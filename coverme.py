# -*- coding: utf-8 -*-
import os
import sys
import json
import yaml

try:
    from urlparse import urlparse
except ImportError:
    import urllib.parse
    urlparse = urllib.parse.urlparse

__version__ = '0.0.1'

class Backup(object):
    def __init__(self, **settings):
        self.settings = settings
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
        pass

    def _new_sources(self, config_list):
        """Create new sources by list of dicts. Return list
        of `BackupSource` objects.
        """
        sources = []
        for c in config_list:
            c_type = c['from']
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
            v_type = v['type']
            if v_type == 'glacier':
                vault = GlacierVault(self, **v)
            elif v_type == 's3':
                vault = S3Vault(self, **v)
            else:
                raise ValueError("Unknown vault type `%s`" % v_type)
            vaults[k] = vault
        return vaults

class BackupSource(object):
    def __init__(self, backup, **settings):
        pass

class PostgresqlBackupSource(BackupSource):
    pass

class MySQLBackupSource(BackupSource):
    pass

class DirBackupSource(BackupSource):
    pass

class BaseVault(object):
    def __init__(self, backup, **settings):
        pass

class GlacierVault(BaseVault):
    pass

class S3Vault(BaseVault):
    pass

if __name__ == '__main__':
    import click
    
    backup, errors = Backup.create_with_config('backup.yml')

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
