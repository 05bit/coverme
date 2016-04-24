# -*- coding: utf-8 -*-
from future.builtins import super
import os
import sys
import json
import yaml
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

class Backup(object):
    def __init__(self, **settings):
        self.defaults = settings.get('defaults', {})
        self.sources = self._new_sources(settings['backups'])
        self.vaults = self._new_vaults(settings['vaults'])

    @classmethod
    def create_with_config(cls, path, file_format=None):
        """Read config and create backup instance with config.
        Return 2-tuple: (instance, errors)

        If configuration contais errors, `instance` is not created,
        and `errors` is a dict with error keys and readable
        descriptions.
        """
        name, ext = os.path.splitext(path)
        if not file_format:
            if ext in ('.json',):
                file_format = 'json'
            else:
                file_format = 'yaml'

        load = yaml.load if file_format == 'yaml' else json.loads

        with open(path) as f:
            settings = load(f)

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
            arch_path = self.archive(source)

    def archive(self, source):
        """Copy data from source and make archive. Return archive path.
        """
        temp_dir = self._make_temp_dir(source.get_base_name())
        not_empty = source.copy_data(temp_dir)
        if not_empty:
            arch_path = self._make_archive(temp_dir)
            print('Archived %s' % arch_path)
        else:
            arch_path = None
            print("Nothing to archive from source %s" % source)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return arch_path

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
            v_type = v.get('type')
            if v_type == 'glacier':
                vault = GlacierVault(self, **v)
            elif v_type == 's3':
                vault = S3Vault(self, **v)
            else:
                if v_type:
                    raise ValueError("Unknown vault type `%s`" % v_type)
                else:
                    raise ValueError("Key `type` is missing for vault `%s`" % k)
            vaults[k] = vault
        return vaults

    def _make_temp_dir(self, prefix):
        """Make temp directory under temp base path.
        """
        base_dir = os.path.realpath(self.defaults['tmpdir'])
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        return tempfile.mkdtemp(prefix=prefix, dir=base_dir)

    def _make_archive(self, dir_name):
        """Make archive of directory.
        """
        arch_format = self.defaults.get('format', 'zip')
        return shutil.make_archive(dir_name,
                                   root_dir=dir_name,
                                   base_dir=None,
                                   format=arch_format)

class BackupSource(object):
    def __init__(self, backup, **settings):
        self.backup = backup
        self.settings = settings

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
            'US': now.microsecond,
            'tags': self.settings['tags'],
        }
        return self.settings['name'].format(**params)

class PostgresqlBackupSource(BackupSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = urlparse(self.settings['url'])
        self.db = self.url.path.strip('/')
        if not self.db:
            raise ValueError("Database is not defined %s" %
                self.settings['url'])

    def copy_data(self, temp_dir):
        """Make database dump via `pg_dump`. Return `True` if not empty.
        """
        dump_file = os.path.join(temp_dir, self.get_base_name())
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

    def __str__(self):
        return '%s://%s%s' % (self.url.scheme, self.url.hostname, self.url.path)

class MySQLBackupSource(BackupSource):
    def copy_data(self, temp_dir):
        """Make database dump via `mysqldump` and return archive path.
        """
        pass

class DirBackupSource(BackupSource):
    def copy_data(self, temp_dir):
        """Make directory archive and return archive path.
        """
        pass

    def __str__(self):
        return self.settings['path']

class BaseVault(object):
    def __init__(self, backup, **settings):
        pass

class GlacierVault(BaseVault):
    pass

class S3Vault(BaseVault):
    pass

if __name__ == '__main__':
    import click

    @click.command()
    @click.option('--config', default='backup.yml',
                  help="Backups configuration file.")
    def main(config):
        backup, errors = Backup.create_with_config(config)

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
        else:
            backup.run()

    main()
