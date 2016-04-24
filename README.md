coverme
=======

Lightweight and easy configurable backup utility.

Install
-------

Instal via pip:

```
pip install coverme
```

or if only Python3.x pip is available: 

```
pip3 install coverme
```

Quickstart
----------

1. Define your backup rules in JSON or YAML config, e.g. `backup.yml`:

    ```yaml
    ---
    backups:
      - from: database
        url: postgres://postgres:127.0.0.1/test
        to: [bucket1]
        name: myapp-{yyyy}-{mm}-{dd}--{HH}-{MM}.sql
        format: zip             # optional, default: gztar
        tags: myapp, db         # optional, no default

      - from: dir
        path: /home/myapp/var/www/uploads
        to: [glacier1]
        name: myapp-{yyyy}-{mm}-{dd}--{HH}-{MM}
        format: zip             # optional, default: gztar
        tags: myapp, uploads    # optional, no default

    vaults:
      bucket1:
        type: s3
        region: eu-west-1
        vault: my-bucket-name  

      glacier1:
        type: glacier
        region: eu-west-1
        vault: my-vault-name
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

License
-------

Copyright (c) 2016, Alexey Kinëv <rudy@05bit.com>

Licensed under The Apache License Version 2.0, January 2004 (Apache-2.0),
see LICENSE file for more details.
