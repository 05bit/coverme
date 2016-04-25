# -*- coding: utf-8 -*-
from future.builtins import super
import os
import sys
import json
import yaml
import logging
import datetime
import shutil
import subprocess
import tempfile

try:
    from urlparse import urlparse
except ImportError:
    import urllib.parse
    urlparse = urllib.parse.urlparse

__version__ = '0.0.1'

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def _stdout_logging():
    """Setup logging to stdout.
    """
    formatter = logging.Formatter(
        '%(levelname)s %(asctime)s %(module)s %(funcName)s(): %(message)s',
        '%Y-%m-%d %H:%M:%S')
    stdout = logging.StreamHandler()
    stdout.setLevel(logging.INFO)
    stdout.setFormatter(formatter)
    log.addHandler(stdout)
    return log.info

echo = _stdout_logging() # Use echo() instead of print() or log.info()

class Backup(object):
    def __init__(self, **settings):
        self.defaults = settings.get('defaults', {})
        self.sources = self._new_sources(settings['backups'])
        self.vaults = self._new_vaults(settings['vaults'])

    @classmethod
    def create_with_config(cls, path=None, stream=None, file_format=None):
        """Read config and create backup instance with config.
        Return 2-tuple: (instance, errors)

        If configuration contais errors, `instance` is not created,
        and `errors` is a dict with error keys and readable
        descriptions.
        """
        if path:
            name, ext = os.path.splitext(path)
            if not file_format:
                if ext in ('.json',):
                    file_format = 'json'
                else:
                    file_format = 'yaml'

            load = yaml.load if file_format == 'yaml' else json.loads

            try:
                with open(path) as f:
                    echo("Reading config from %s" % path)
                    settings = load(f)
            except IOError:
                return None, {'path': path, '': "No config file found"}
        elif stream:
            echo("Reading config from stdin")
            text = '\n'.join([line for line in stream])
            if text.startswith('---'):
                settings = yaml.load(text)
            else:
                settings = json.loads(text)
        else:
            raise Exception("Either config path or stream must be provided.")

        errors = cls.validate(**settings)
        if not errors:
            try:
                return cls(**settings), None
            except Exception as e:
                errors = {'': e}

        errors['path'] = path
        return None, errors

    @classmethod
    def validate(cls, **settings):
        """Validate settings and show human readable (not developer
        readable) errors.
        """
        errors = {}
        if not settings.get('backups'):
            errors['backups'] = "Section `backups` is empty"
        if not settings.get('vaults'):
            errors['vaults'] = "Section `vaults` is empty"
        return errors

    def run(self):
        """Run backup for all sources.
        """
        for source in self.sources:
            temp_dir = self._make_temp_dir()
            arch_path = source.archive(temp_dir)
            if arch_path:
                vault_keys = source.get_vault_keys()
                if vault_keys[0] == '*':
                    vault_keys = self.vaults.keys()
                for k in vault_keys:
                    vault = self.vaults[k]
                    success, data = vault.upload(arch_path)
                    if success:
                        echo("Uploaded to %s: %s" % (vault, data))
                    else:
                        echo("Not uploaded to %s" % vault)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def get_temp_dir(self):
        """Get base temp directory path.
        """
        return os.path.realpath(self.defaults.get('tmpdir', '/tmp'))

    def _new_sources(self, config_list):
        """Create new sources by list of dicts. Return list
        of `BackupSource` objects.
        """
        sources = []
        for c in config_list:
            c_type = c.get('type')
            if c_type == 'database':
                url = urlparse(c['url'])
                if url.scheme == 'postgres':
                    source = PostgresqlBackupSource(self, **c)
                elif url.scheme == 'mysql':
                    source = MySQLBackupSource(self, **c)
                else:
                    raise ValueError("Unknown database source scheme `%s`"
                        % url.scheme)
            elif c_type == 'dir':
                source = DirBackupSource(self, **c)
            sources.append(source)
        return sources

    def _new_vaults(self, config_dict):
        """Create new vaults by dict. Return dict
        of `BaseVault` objects.
        """
        vaults = {}
        for k, v in config_dict.items():
            v_service = v.get('service')
            if v_service == 'glacier':
                vault = GlacierVault(self, **v)
            elif v_service == 's3':
                vault = S3Bucket(self, **v)
            else:
                if v_service:
                    raise ValueError("Unknown vault service `%s`" % v_service)
                else:
                    raise ValueError("Key `service` is missing for vault `%s`" % k)
            vaults[k] = vault
        return vaults

    def _make_temp_dir(self, prefix=''):
        """Make new temp directory under base temp path.
        """
        base_dir = self.get_temp_dir()
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        return tempfile.mkdtemp(dir=base_dir, prefix=prefix)

class BackupSource(object):
    def __init__(self, backup, **settings):
        self.backup = backup
        self.settings = settings

    def archive(self, temp_dir):
        """Copy data from source and make archive within temp directory.
        """
        data_dir = os.path.join(temp_dir, self.get_base_name())
        os.makedirs(data_dir)
        not_empty = self.copy_data(data_dir)
        if not_empty:
            arch_path = self._make_archive(data_dir)
            echo("Archived %s" % arch_path)
        else:
            arch_path = None
            echo("Nothing to archive from source %s" % self)
        return arch_path

    def copy_data(self, data_dir):
        """Copy backup data to temp directory.
        """
        raise NotImplementedError

    def get_vault_keys(self):
        """Get vaults keys to upload archive. If not specified in config,
        return ['*'] which mean all available vaults.
        """
        return self.settings.get('to', ['*'])

    def get_base_name(self):
        """Get base name for archive.
        """
        now = datetime.datetime.now()
        params = {
            'yyyy': now.year,
            'mm': '%02d' % now.month,
            'dd': '%02d' % now.day,
            'HH': '%02d' % now.hour,
            'MM': '%02d' % now.minute,
            'SS': '%02d' % now.second,
            'UU': now.microsecond,
            'tags': self.settings['tags'],
        }
        return self.settings['name'].format(**params)

    def _make_archive(self, dir_name):
        """Make archive of directory.
        """
        arch_format = self.backup.defaults.get('format', 'zip')
        return shutil.make_archive(dir_name,
                                   root_dir=dir_name,
                                   base_dir=None,
                                   format=arch_format)

class DbSource(BackupSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = urlparse(self.settings['url'])
        self.db = self.url.path.strip('/')
        if not self.db:
            raise ValueError("Database is not defined %s" %
                self.settings['url'])

    def __str__(self):
        return '%s://%s%s' % (self.url.scheme, self.url.hostname, self.url.path)

class PostgresqlBackupSource(DbSource):
    def copy_data(self, data_dir):
        """Make database dump via `pg_dump`. Return `True` if not empty.
        """
        dump_file = os.path.join(data_dir, self.get_base_name())
        args = ['pg_dump', '--file=%s' % dump_file]
        if self.url.port:
            args.append('--port=%s' % self.url.port)
        if self.url.hostname:
            args.append('--host=%s' % self.url.hostname)
        if self.url.username:
            args.append('--username=%s' % self.url.username)
        args.append(self.db)
        result = subprocess.call(args)
        return (result == 0)

class MySQLBackupSource(DbSource):
    def copy_data(self, data_dir):
        """Make database dump via `mysqldump` and return archive path.
        """
        dump_file = os.path.join(data_dir, self.get_base_name())
        args = ['mysqldump', '--result-file=%s' % dump_file]
        if self.url.port:
            args.append('--port=%s' % self.url.port)
        if self.url.hostname:
            args.append('--host=%s' % self.url.hostname)
        if self.url.username:
            args.append('--user=%s' % self.url.username)
        if self.url.password:
            args.append('--password=%s' % self.url.password)
        args.append(self.db)
        result = subprocess.call(args)
        return (result == 0)

class DirBackupSource(BackupSource):
    def copy_data(self, data_dir):
        """Make directory archive and return archive path.
        """
        pass

    def __str__(self):
        return self.settings['path']

class BaseVault(object):
    def __init__(self, backup, **settings):
        self.backup = backup
        self.settings = settings

class AWSVault(object):
    def __init__(self, backup, **settings):
        self.backup = backup
        self.settings = settings
        params = {
            'region': settings.get('region'),
            'access_key_id': settings.get('access_key_id'),
            'secret_access_key': settings.get('secret_access_key'),
        }
        self.service = self._aws_service(settings['service'], **params)

    @staticmethod
    def _aws_service(name, region=None,
                     access_key_id=None,
                     secret_access_key=None):
        """Get `boto3` Amazon service manager, e.g. S3 or Glacier.

        Example:

            s3 = get_aws_service('s3')
        """
        import boto3
        return boto3.resource(name, region_name=region,
                              aws_access_key_id=access_key_id,
                              aws_secret_access_key=secret_access_key)

class GlacierVault(AWSVault):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        account_id = self.settings.get('account', '')
        name = self.settings.get('name')
        self.vault = self.service.Vault(str(account_id), name)

    def __str__(self):
        return "Amazon Glacier [%(region)s] %(name)s" % {
            'name': self.vault.name,
            'region': self.settings.get('region', 'default region')
        }

    def upload(self, archive_path):
        """Upload archive to Amazon Glacier. Return 2-tuple:
        ((bool) success, (dict) archive data).
        """
        # self.vault.load()
        with open(archive_path, 'rb') as data:
            description = os.path.basename(archive_path)
            archive = self.vault.upload_archive(
                body=data, archiveDescription=description)
        if archive:
            return True, {'id': archive.id, 'description': description}
        else:
            return False, None

class S3Bucket(AWSVault):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        name = self.settings.get('name')
        self.bucket = self.service.Bucket(name)

    def __str__(self):
        return "Amazon S3 %(name)s" % self.settings

    def upload(self, archive_path):
        """Upload archive to Amazon S3. Return 2-tuple:
        ((bool) success, (dict) archive data).
        """
        key = os.path.basename(archive_path)
        with open(archive_path, 'rb') as data:
            obj = self.bucket.put_object(
                ACL='private', Body=data, Key=key)
        if obj:
            return True, {'key': obj.key}
        else:
            return False, None

def main():
    """Command-line interface for coverme.
    """
    import click

    global echo

    def nice_echo(message):
        click.echo('* %s' % message)

    echo = nice_echo

    def get_params(config):
        if config == '-':
            return {'stream': sys.stdin}
        else:
            return {'path': config}

    @click.group()
    @click.pass_context
    def cli(ctx):
        """Command-line interface for coverme.
        """
        pass

    @cli.command()
    @click.option('-c', '--config', show_default=True, default='backup.yml',
                  help="Backups configuration file."
                       "Specify '-' to read from STDIN.")
    @click.pass_context
    def backup(ctx, config):
        params = get_params(config)
        backup, errors = Backup.create_with_config(**params)

        if errors:
            path = errors.pop('path')
            click.echo("Errors in configuration file `%s`" % path)
            for k, v in errors.items():
                click.echo("- %s" % v)
            click.echo("\n"
                       "    Run `coverme --help` for basic examples\n"
                       "    See also README.md and docs for details\n"
                       "    https://github.com/05bit/coverme\n")
            sys.exit(1)

        backup.run()

    try:
        cli()
    except Exception as e:
        click.echo("\n"
                   "Exited with error! %s" % e)
        sys.exit(1)

if __name__ == '__main__':
    main()
