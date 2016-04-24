# -*- coding: utf-8 -*-
import os
import sys
import json
import yaml
import click

__version__ = '0.0.1'

class Backup(object):
    def __init__(self, **settings):
        self.sources = self.get_sources(settings['backups'])
        self.settings = settings
        print(settings)
        pass

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

        errors = cls.validate(path, **settings)

        if not errors:
            return cls(**settings), None
        else:
            return None, errors

    @classmethod
    def validate(cls, path, **settings):
        """Validate settings and show human readable (not developer
        readable) errors.
        """
        errors = {}
        if not settings.get('backups'):
            errors['backups'] = "section is empty, should be a list of sources"
        if errors:
            errors['path'] = path
        return errors

    def run(self):
        pass

    def get_sources(self, *configs):
        pass


class BackupSource(object):
    def __init__(self, backup, **settings):
        pass

class PostgresqlBackupSource(BackupSource):
    pass

class MySQLBackupSource(BackupSource):
    pass

class DirBackupSource(BackupSource):
    pass

if __name__ == '__main__':
    backup, errors = Backup.create_with_config('backup.yml')

    if errors:
        path = errors.pop('path')
        click.echo("Errors in configuration file `%s`" % path)
        for k, v in errors.items():
            click.echo("- %s: %s" % (k, v))
        click.echo("\n"
                   "    Run `coverme --help` for basic examples\n"
                   "    See also README.md and docs for details\n"
                   "    https://github.com/05bit/coverme\n")
        sys.exit(1)
    else:
        backup.run()
