beancount-importer
==================

Various custom importers for `beancount`_.

See the `list of supported importers`_.

Installation
------------

.. code-block:: console

    $ pipx install beancount-importers

Usage
-----

``beancount-importer`` expects to be run from within your ledger folder, with a
``config.toml`` file configured with your account details and your patterns.
The file format accepts an optional ``beancount-importer.patterns`` list
containing items in the following format::

    [
        'narration' | 'payee' | 'either' | 'both',
        'Account:Name',
        '^regex$',
    ]

Note that if using the ``both`` target kind, the payee and narration will be
concatendated with a semicolon (``;``) for the purpose of parsing, eg.::

    ['both', 'Income:Salary', '^My Company;Salary$'],

If ``beancount-importer.patterns`` is specified, all definitions in that list
will be applied to all your accounts. In this file, you should also list each
of your accounts, eg.

.. code-block:: toml

    [[beancount-importer.paypal]]
    account = 'Assets:Paypal'

    [[beancount-importer.tangerine]]
    account = 'Assets:Tangerine:Checking'
    lastfour = '1234'

    [[beancount-importer.tangerine]]
    account = 'Liabilities:Tangerine:Mastercard'
    lastfour = '5678'
    patterns = [...]

You can specify any number of accounts, including multiple of the same kind, so
long as they parse with separate filenames. This will be verified when you run
``identify`` -- any ambiguous filenames will produce an error, in which case
you'll need to handle those accounts separately. The ``patterns`` list follows
the same parsing as the above global ``patterns`` object and is optional on a
per-account basis; if specified, those patterns will be appended to your global
pattern list and apply only to this account.

.. code-block:: console

    $ cd /my-beancount/ledger
    $ cat config.toml
    [beancount-importer]
    patterns = [
        ['payee', 'Income:Salary', '^My Employer.*$'],
    ]

    [[beancount-importer.tangerine]]
    account = 'Assets:Tangerine:Checking'
    lastfour = '1234'
    patterns = [
        ['payee', 'Income:Tangerine:Checking:Interest', '^Interest Paid$'],
    ]

    # Check downloaded files for errors
    $ bean-import identify -v ~/Downloads

    # Reconcile issues, fix parsing, adjust patterns, etc
    $ bean-import extract -xe index.beancount ~/Downloads
    $ vim
    $ # ...repeat until no errors...

    # Actually import the new data
    $ bean-import extract -e index.beancount -o my-ledger.beancount ~/Downloads

    # Archive parsed statements
    $ bean-import archive -o docs ~/Downloads

    # Verify everything reconciled properly (command provided by beancount)
    $ bean-check index.beancount

    # View your ledger (command provided by fava)
    $ fava index.beancount

.. _beancount: https://beancount.github.io/
.. _list of supported importers: https://github.com/TheKevJames/beancount-importer/blob/master/beancount_importer/__init__.py
