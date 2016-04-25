coverme
=======

Lightweight and easy configurable server backup utility.

- [Install](#install)
- [Usage](#usage)
- [Tips on Amazon services setup](#tips-on-amazon-services-setup)
- [License](#license)

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

Usage
-----

Just to make sure that installation is correct run:

```
coverme --help
```

**Please note!** The examples below do not provide best security practices! Intermediate backups are stored in shared `/tmp` dir and backups are not encrypted.

1. Define your backup rules in JSON or YAML config, e.g. `backup.yml`:

    ```yaml
    ---
    defaults:
        # tmpdir: base directory for temporary files
        tmpdir: tmp
        # cleanup: remove archive after upload or not, default: no
        cleanup: yes
        # format: optional, default: zip
        format: gztar

    backups:
      - type: database
        url: postgres://postgres@127.0.0.1:5432/test
        to: [bucket1]
        name: postgres-{yyyy}-{mm}-{dd}--{HH}-{MM}.sql
        # tags: optional, no default
        tags: myapp, postgres, db

      - type: database
        url: mysql://root@127.0.0.1/test
        to: [bucket1]
        name: mysql-{yyyy}-{mm}-{dd}--{HH}-{MM}.sql
        # tags: optional, no default
        tags: myapp, mysql, db

      - type: dir
        path: /home/myapp/var/www/uploads
        to: [glacier1]
        name: myapp-{yyyy}-{mm}-{dd}--{HH}-{MM}
        # format: optional, default: zip
        format: gztar
        # tags: optional, no default
        tags: myapp, uploads

    vaults:
      bucket1:
        service: s3
        region: eu-west-1
        account: NNNNNNNNNNNN
        bucket: coverme-test

      glacier1:
        service: glacier
        region: eu-west-1
        account: NNNNNNNNNNNN
        vault: coverme-test
    ...
    ```

2. Perform test backup using config file `backup.yml`:

    ```
    coverme -c backup.yml
    ```

    If some configutaion error happen, fix it first. For example, may you have to configure AWS credentials with [`aws configure`](http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html) first.

3. Add `coverme` to cron jobs:

    ```
    crontab -e
    ```

    Make sure to specify full paths to files, because cron jobs are run without PATH environment setting by default:

    ```
    # run coverme backups every day at 5:30
    30 5 * * * /usr/local/bin/coverme -c /home/myapp/backup.yml
    ```

    Real path to `coverme` may be different depending on installation, to get proper full path run:

    ```
    which coverme
    ```

Tips on Amazon services setup
-----------------------------

### How to install `aws` Amazon command line utility?

```
pip install awscli
```

### How to create Amazon Glacier vault?

You may create vaults using wizard:  
https://console.aws.amazon.com/glacier/home

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

### How to grant user access to Glacier?

In Amazon Identity and Access Management (IAM) panel on user's details page:  
_Permissions tab_ -> _Inline Policies_ (click to expand) -> **Create User Policy**

Then choose _Policy Generator_, and then:

- Select "Amazon Glacier" in dropdown
- Check required pesmissions or mark all
- Specify Glacier vault identifier, like that `arn:aws:glacier:eu-west-1:NNNNNNNNNNNN:vaults/coverme-test`, vault should be creatd first!

### How to grant user access to S3?

In Amazon Identity and Access Management (IAM) panel on user's details page:  
_Permissions tab_ -> _Inline Policies_ (click to expand) -> **Create User Policy**

Then choose _Policy Generator_, and then:

- Select "Amazon S3" in dropdown
- Check required pesmissions or mark all
- Specify S3 bucket ARN mask, like that `arn:aws:s3:::coverme-test/*`

License
-------

Copyright (c) 2016, Alexey Kinëv <rudy@05bit.com>

Licensed under The Apache License Version 2.0, January 2004 (Apache-2.0),
see LICENSE file for more details.
