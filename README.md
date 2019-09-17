coverme
=======

Lightweight and easy configurable server backup utility.

- [Install](#install)
- [Basic usage](#basic-usage)
- [Questions and answers](#questions-and-answers)
- [Command line help](#command-line-help)
- [Tips on Amazon services setup](#tips-on-amazon-services-setup)
- [License](#license)

Overview
--------

`coverme` acts as a backup data aggregator, it grabs data from different sources and uploads it to Amazon Glacier or Amazon S3. More storage options will be probably available. You're always welcome to fork and make a pull request ;)

* Requires Python 2.7+ or Python 3.4+ installed
* Should work on Linux/MacOS/FreeBSD
* Supports MySQL backups via `mysqldump`
* Supports PostgreSQL backups via `pg_dump`
* Supports directory archive
* Uploading backups to Amazon S3 as private objects
* Uploading to Amazon Glacier
* Schedule backups via `crontab` or run manually

Also for Amazon services configuration you may need to install AWS command line utility `awscli`.

Install
-------

Install via pip:

```
pip install coverme
```

or if only Python 3.x pip is available: 

```
pip3 install coverme
```

If you're going to use Amazon services for backup, you'll also need to set up credentials via `aws configure` or manually, see [Tips on Amazon services setup](#tips-on-amazon-services-setup).

Basic usage
-----------

Just to make sure that installation is correct run:

```
coverme --help
```

**Please note!** Examples below probably do not provide best security practices! Intermediate backups are stored in shared `/tmp` dir and backups are not encrypted before upload.

1. Define your backup rules in JSON or YAML config, e.g. `backup.yml`:

    ```yaml
    ---
    defaults:
        # tmpdir - base directory for temporary files
        tmpdir: /tmp
        # cleanup - remove archive after upload or not, default: no
        cleanup: yes
        # localdir - optional, directory for local backups
        localdir: backups
        # format - optional, default: zip
        format: gztar

    backups:
      - type: database
        url: postgres://postgres@127.0.0.1:5432/test
        to: [bucket1]
        name: postgres-{yyyy}-{mm}-{dd}--{HH}-{MM}.sql
        # tags - optional, no default
        tags: myapp, postgres, db

      - type: database
        url: mysql://root@127.0.0.1/test
        to: [bucket1]
        name: mysql-{yyyy}-{mm}-{dd}--{HH}-{MM}.sql
        # tags - optional, no default
        tags: myapp, mysql, db

      - type: dir
        path: /home/myapp/var/www/uploads
        to: [glacier1]
        name: myapp-{yyyy}-{mm}-{dd}--{HH}-{MM}
        # format - optional, default: zip
        format: gztar
        # tags - optional, no default
        tags: myapp, uploads

    vaults:
      bucket1:
        service: s3
        region: eu-west-1
        # profile - optional, AWS configuration profile
        # profile: coverme
        name: coverme-test

      glacier1:
        service: glacier
        region: eu-west-1
        account: NNNNNNNNNNNN
        name: coverme-test
    ...
    ```

2. Perform test backup using config file `backup.yml`:

    ```
    coverme backup -c backup.yml
    ```

    If some configutaion error happen, fix it first. For example, may you have to configure AWS credentials with [`aws configure`](http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html) first.

3. Add `coverme` to cron jobs:

    ```
    crontab -e
    ```

    Make sure to add PATH environment setting, so cron script could found `pg_dump`, `mysqldump` and other shell commands:

    ```
    SHELL=/bin/sh
    PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

    # run coverme backups every day at 5:30
    30 5 * * * /usr/local/bin/coverme backup -c /home/myapp/backup.yml
    ```

    Real path to `coverme` may be different depending on installation, to get proper full path run:

    ```
    which coverme
    ```

Usage with Docker
-----------------

Docker container is available as [rudyryk/coverme](https://cloud.docker.com/u/rudyryk/repository/docker/rudyryk/coverme).

Here's an example for using in `docker-compose.yml`:

```yaml
  # ... your services

  coverme:
    image: rudyryk/coverme
    restart: unless-stopped
    depends_on:
      - postgres
    environment:
      PGPASSWORD: ${PGPASSWORD}
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
    volumes:
      - ./coverme/config.yml:/etc/coverme/config.yml
```

Questions and answers
---------------------

### How to provide PostgreSQL password for `pg_dump`?

Use `~/.pgpass` file with `600` permissions, see details here:  
http://www.postgresql.org/docs/current/static/libpq-pgpass.html

### How to rotate my backups?

It's easy to rotate backups using name pattern. For example, specify
`mysql/dump-{dd}.sql` as name for MySQL dump archive and you will get
sequence of files like that:

    mysql/dump-01.sql (for 1st day of month)
    mysql/dump-02.sql (for 2nd day of month)
    ...
    mysql/dump-31.sql (for 31st day of month)

So you will get monthly backups rotation. Some months have 31 day while others have 30 or 28/29, but that should not be a real issue in most cases.

Command line help
-----------------

Get list of available commands:

```
$ coverme --help

Usage: coverme [OPTIONS] COMMAND [ARGS]...

  Command-line interface for coverme.

Options:
  --help  Show this message and exit.

Commands:
  backup
```

Get help for `backup` command:

```
$ coverme backup --help

Usage: coverme backup [OPTIONS]

Options:
  -c, --config TEXT  Backups configuration file.Specify '-' to read from
                     STDIN.  [default: backup.yml]
  --help             Show this message and exit.
```


Tips on Amazon services setup
-----------------------------

### How to install `aws` Amazon command line utility?

```
pip install awscli
```

### How to set up Amazon credentials?

```
aws configure
```

or manually save credentials to `~/.aws/credentials`:

```
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY

[another]
; Just a custom profile called 'another', optional section
aws_access_key_id = YOUR_ANOTHER_ACCESS_KEY
aws_secret_access_key = YOUR_ANOTHER_SECRET_KEY
```

### How to get Amazon credentials?

Use Amazon Identity and Access Management (IAM) service to manage users:  
https://console.aws.amazon.com/iam/home#users

### How to create Amazon Glacier vault?

You may create vaults using wizard:  
https://console.aws.amazon.com/glacier/home

### How to grant user access to Glacier?

In Amazon Identity and Access Management (IAM) panel on user's details page:  
_Permissions tab_ -> _Inline Policies_ (click to expand) -> **Create User Policy**

Choose _Policy Generator_ and then:

- Select "Amazon Glacier" in dropdown
- Check required pesmissions or mark all
- Specify Glacier vault identifier, e.g. `arn:aws:glacier:eu-west-1:NNNNNNNNNNNN:vaults/coverme-test`, vault should be created first

### How to grant user access to S3?

In Amazon Identity and Access Management (IAM) panel on user's details page:  
_Permissions tab_ -> _Inline Policies_ (click to expand) -> **Create User Policy**

Choose _Policy Generator_ and then:

- Select "Amazon S3" in dropdown
- Check required pesmissions or mark all
- Specify S3 bucket resources mask, e.g. `arn:aws:s3:::coverme-test/*`

License
-------

Copyright (c) 2016, Alexey Kinëv <rudy@05bit.com>

Licensed under The Apache License Version 2.0, January 2004 (Apache-2.0),
see LICENSE file for more details.
