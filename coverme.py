# -*- coding: utf-8 -*-
try:
    from future.builtins import super
except ImportError:
    pass
import os
import sys
import json
import logging
import datetime
import shutil
import subprocess
import tempfile
import yaml

try:
    from urlparse import urlparse
except ImportError:
    import urllib.parse
    urlparse = urllib.parse.urlparse

__version__ = '0.6.2'

log = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = {
    'zip': '.zip',
    'tar': '.tar',
    'gztar': '.tar.gz',
    'bztar': '.tar.bz2',
}

def register_archive_extension(archive_type, ext):
    """Register new archive type file name extension, e.g.
    register_archive_extension('7z', '.7z')

    This should be used together with `shutil.register_archive_format()`
    to properly construct archive names for uploads.
    """
    return ARCHIVE_EXTENSIONS.setdefault(archive_type, ext)

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
            _, ext = os.path.splitext(path)
            if not file_format:
                if ext in ('.json',):
                    file_format = 'json'
                else:
                    file_format = 'yaml'

            load = yaml.safe_load if file_format == 'yaml' else json.loads

            try:
                with open(path) as fp:
                    settings = load(fp)
                    echo("... reading config from %s" % path)
            except IOError:
                return None, {'path': path, '': "No config file found"}
        elif stream:
            echo("Reading config from stdin")
            text = '\n'.join([line for line in stream])
            if text.startswith('---'):
                settings = yaml.safe_load(text)
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
        echo("... started at [%s]" % datetime.datetime.now())
        for source in self.sources:
            temp_dir = _smaketemp(self.get_temp_dir())
            try:
                self._run_with_temp_dir(source, temp_dir)
            except Exception as e:
                echo('*** error in %s: %s' % (source, e))
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        echo("... completed at [%s]" % datetime.datetime.now())

    def get_temp_dir(self):
        """Get base temp directory path.
        """
        return os.path.realpath(self.defaults.get('tmpdir', '/tmp'))

    def get_local_dir(self):
        """Get directory path for local backups.
        """
        localdir = self.defaults.get('localdir')
        if localdir:
            return os.path.realpath(localdir)

    def _run_with_temp_dir(self, source, temp_dir):
        """Run backup for source within temp directory.
        """
        arch_path = source.archive(temp_dir)
        if arch_path:
            upload_name = source.get_archive_fullname()
            vault_keys = source.get_vault_keys()
            if vault_keys[0] == '*':
                vault_keys = self.vaults.keys()
            for k in vault_keys:
                vault = self.vaults[k]
                success, data = vault.upload(arch_path,
                                             upload_name=upload_name)
                if success:
                    echo("+++ uploaded to %s: %s" % (vault, data))
                else:
                    echo("*** not uploaded to %s" % vault)
            base_local_dir = source.get_local_dir()
            if base_local_dir:
                local_dir = os.path.join(base_local_dir,
                                         os.path.dirname(upload_name))
                _smove(arch_path, local_dir)
                echo("+++ local backup saved to %s" % local_dir)
        else:
            echo("*** nothing to upload from source %s" % source)

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

class BackupSource(object):
    def __init__(self, backup, **settings):
        self.backup = backup
        self.settings = settings
        self.name_pattern = self.settings.get('name')
        if not self.name_pattern:
            raise ValueError("Missing 'name' key in config for %s" % self)

    def archive(self, temp_dir):
        """Copy data from source and make archive within temp directory.
        """
        data_dir = self._prepare_data_path(temp_dir)
        not_empty = self.copy_data(data_dir)
        if not_empty:
            arch_path = self._make_archive(data_dir)
            echo("... archived %s" % arch_path)
        else:
            arch_path = None
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

    def get_archive_format(self):
        """Get archive format.
        """
        default_format = self.backup.defaults.get('format')
        return self.settings.get('format', default_format) or 'zip'

    def get_archive_basename(self):
        """Get base name for archive without extension, e.g. for MySQL
        dump archive it could return `mysql-2016-10-20.sql` and the derived
        zip-archive will have name `mysql-2016-10-20.sql.zip`.
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
            'tags': self.settings.get('tags', ''),
        }
        return self.settings['name'].format(**params)

    def get_archive_fullname(self):
        """Get archive name with extension, e.g. for MySQL
        dump archive it could return `mysql-2016-10-20.sql`.

        The name pattern configured as `name` parameter in backup
        source definition in config.
        """
        name = self.get_archive_basename()
        aformat = self.get_archive_format()
        ext = ARCHIVE_EXTENSIONS.get(aformat)
        if not ext:
            ext = '.%s' % aformat
            log.warning("*** archive format `%s` is not registered with"
                        " `register_archive_extension()`" % aformat)
        return name + ext

    def get_local_dir(self):
        """Get directory path for local backups.
        """
        default = self.backup.get_local_dir()
        localdir = self.settings.get('localdir', default)
        if localdir:
            return os.path.realpath(localdir)

    def _make_archive(self, dir_name):
        """Make archive of the specified directory near that directory.
        """
        return shutil.make_archive(dir_name,
                                   root_dir=dir_name,
                                   base_dir=None,
                                   format=self.get_archive_format())

    def _prepare_data_path(self, base_dir):
        """Join base dir with :meth:`.get_archive_basename()` and create
        all parent dirs in the resulting tree. Return joined path.
        """
        path = os.path.join(base_dir, self.get_archive_basename())
        _smakedirs(os.path.dirname(path))
        return path

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
        dump_file = self._prepare_data_path(data_dir)
        args = ['pg_dump', '--file=%s' % dump_file]
        if self.url.port:
            args.append('--port=%s' % self.url.port)
        if self.url.hostname:
            args.append('--host=%s' % self.url.hostname)
        if self.url.username:
            args.append('--username=%s' % self.url.username)
        options = self.settings.get('options')
        if options:
            args += options.split(' ')
        args.append(self.db)
        echo("... %s with options %s" % (args[0], options or '(none)'))
        result = subprocess.call(args, stderr=subprocess.STDOUT)
        return (result == 0)

class MySQLBackupSource(DbSource):
    def copy_data(self, data_dir):
        """Make database dump via `mysqldump` and return archive path.
        """
        dump_file = self._prepare_data_path(data_dir)
        args = ['mysqldump', '--result-file=%s' % dump_file]
        if self.url.port:
            args.append('--port=%s' % self.url.port)
        if self.url.hostname:
            args.append('--host=%s' % self.url.hostname)
        if self.url.username:
            args.append('--user=%s' % self.url.username)
        if self.url.password:
            args.append('--password=%s' % self.url.password)
        options = self.settings.get('options')
        if options:
            args += options.split(' ')
        args.append(self.db)
        echo("... %s with options %s" % (args[0], options or '(none)'))
        result = subprocess.call(args, stderr=subprocess.STDOUT)
        return (result == 0)

class DirBackupSource(BackupSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = self.settings.get('path')
        if not self.path:
            raise ValueError("Path not specified for directory "
                             "backup source, 'path' key is empty")

    def archive(self, temp_dir):
        """Archive source directory to temp directory.
        Return archive full path.
        """
        # We want to achive `/my/sub/{some dir}` under unique temp dir:
        # `/tmp/dEdjnr/{name from config}`
        #
        # So we make archive from base path `/my/sub/{some dir}`,
        # root path `/my/sub/` and archive name
        # `/tmp/dEdjnr/{name from config}`
        from_path = self.settings['path']
        base_name = self._prepare_data_path(temp_dir)
        echo("... archive directory %s" % from_path)
        arch_path = shutil.make_archive(
            base_name=base_name,
            root_dir=os.path.dirname(from_path),
            base_dir=from_path,
            # logger=log,
            format=self.get_archive_format())
        echo("... archived %s" % arch_path)
        return arch_path

    def __str__(self):
        return self.settings['path']

class BaseVault(object):
    def __init__(self, backup, **settings):
        self.backup = backup
        self.settings = settings

class AWSVault(object):
    def __init__(self, backup, **settings):
        import boto3.session
        self.backup = backup
        self.settings = settings
        params = {
            'region_name': settings.get('region'),
            'profile_name': settings.get('profile'),
            'aws_access_key_id': settings.get('access_key_id'),
            'aws_secret_access_key': settings.get('secret_access_key'),
        }
        session = boto3.session.Session(**params)
        self.service = session.resource(settings['service'])

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

    def upload(self, archive_path, upload_name=None):
        """Upload archive to Amazon Glacier. Return 2-tuple:
        ((bool) success, (dict) archive data).
        """
        # self.vault.load()
        with open(archive_path, 'rb') as data:
            description = upload_name or os.path.basename(archive_path)
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

    def upload(self, archive_path, upload_name=None):
        """Upload archive to Amazon S3. Return 2-tuple:
        ((bool) success, (dict) archive data).
        """
        key = upload_name or os.path.basename(archive_path)
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

    def nice_echo(msg):
        if msg.startswith('+++'):
            click.secho(msg, fg='green')
        elif msg.startswith('***'):
            click.secho(msg, fg='red', err=True)
        else:
            click.echo(msg)

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
            echo("Errors in configuration file `%s`" % path)
            for k, v in errors.items():
                echo("*** %s" % v)
            echo("\n"
                 "    Run `coverme --help` for basic examples\n"
                 "    See also README.md and docs for details\n"
                 "    https://github.com/05bit/coverme\n")
            sys.exit(1)

        backup.run()

    try:
        cli()
    except Exception as e:
        echo("*** exited with error! %s" % e)
        sys.exit(1)

#########
# Utils #
#########

def _smakedirs(path):
    """Safe `os.makedirs()` shortcut. Check if directory does not exist
    and create with `0o700` permission mode.
    """
    if path and not os.path.exists(path):
        os.makedirs(path, mode=0o700)

def _smaketemp(base_dir, prefix=''):
    """Safe make new temp directory under base temp path.
    """
    _smakedirs(base_dir)
    return tempfile.mkdtemp(dir=base_dir, prefix=prefix)

def _smove(src, dst_dir):
    """Move file to destination directory with overwrite.
    """
    _smakedirs(dst_dir)
    dst_path = os.path.join(dst_dir, os.path.basename(src))
    if os.path.exists(dst_path):
        os.unlink(dst_path)
    shutil.move(src, dst_dir)

def _stdout_logging(level):
    """Setup logging to stdout and return logger's `info` method.
    """
    formatter = logging.Formatter(
        '%(levelname)s %(asctime)s %(module)s %(funcName)s(): %(message)s',
        '%Y-%m-%d %H:%M:%S')
    stdout = logging.StreamHandler()
    stdout.setLevel(level)
    stdout.setFormatter(formatter)
    log.setLevel(level)
    log.addHandler(stdout)
    return log.info

# Use echo() instead of print() or log.info()
echo = _stdout_logging(logging.INFO)

################
# Run the main #
################

if __name__ == '__main__':
    main()
