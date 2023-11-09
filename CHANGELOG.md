Changelog
=========

## 0.8.1

* Better handle environment variables in backup source address

## 0.8

* Changed packaging configuration to `pyproject.toml` format
* Added support for custom `endpoint_url` for AWS resources
* Optional support for `.env` file

## 0.6

* Fix: `tags` for backup source is optional field
* Fix: slash in backup names is respected for local backups and uploads
* Add feature of saving backups locally
* Add support of custom options for `mysqldump` and `pg_dump`

## 0.5

* Initial release with basic features support: MySQL dump, PostgreSQL dump, local directory archive, upload to Amazon S3 and Amazon Glacier
