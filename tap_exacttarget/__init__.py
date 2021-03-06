#!/usr/bin/env python3

import argparse
import json

import singer

from tap_exacttarget.state import load_state, save_state

from tap_exacttarget.client import get_auth_stub

from tap_exacttarget.endpoints.campaigns \
    import CampaignDataAccessObject
from tap_exacttarget.endpoints.content_areas \
    import ContentAreaDataAccessObject
from tap_exacttarget.endpoints.data_extensions \
    import DataExtensionDataAccessObject
from tap_exacttarget.endpoints.emails import EmailDataAccessObject
from tap_exacttarget.endpoints.events import EventDataAccessObject
from tap_exacttarget.endpoints.folders import FolderDataAccessObject
from tap_exacttarget.endpoints.lists import ListDataAccessObject
from tap_exacttarget.endpoints.list_sends import ListSendDataAccessObject
from tap_exacttarget.endpoints.list_subscribers \
    import ListSubscriberDataAccessObject
from tap_exacttarget.endpoints.sends import SendDataAccessObject
from tap_exacttarget.endpoints.subscribers import SubscriberDataAccessObject


LOGGER = singer.get_logger()  # noqa


def validate_config(config):
    required_keys = ['client_id', 'client_secret']
    missing_keys = []
    null_keys = []
    has_errors = False

    for required_key in required_keys:
        if required_key not in config:
            missing_keys.append(required_key)

        elif config.get(required_key) is None:
            null_keys.append(required_key)

    if missing_keys:
        LOGGER.fatal("Config is missing keys: {}"
                     .format(", ".join(missing_keys)))
        has_errors = True

    if null_keys:
        LOGGER.fatal("Config has null keys: {}"
                     .format(", ".join(null_keys)))
        has_errors = True

    if has_errors:
        raise RuntimeError


def load_catalog(filename):
    catalog = {}

    try:
        with open(filename) as handle:
            catalog = json.load(handle)
    except Exception:
        LOGGER.fatal("Failed to decode catalog file. Is it valid json?")
        raise RuntimeError

    return catalog


def load_config(filename):
    config = {}

    try:
        with open(filename) as handle:
            config = json.load(handle)
    except Exception:
        LOGGER.fatal("Failed to decode config file. Is it valid json?")
        raise RuntimeError

    validate_config(config)

    return config


AVAILABLE_STREAM_ACCESSORS = [
    CampaignDataAccessObject,
    ContentAreaDataAccessObject,
    DataExtensionDataAccessObject,
    EmailDataAccessObject,
    EventDataAccessObject,
    FolderDataAccessObject,
    ListDataAccessObject,
    ListSendDataAccessObject,
    ListSubscriberDataAccessObject,
    SendDataAccessObject,
    SubscriberDataAccessObject,
]


def do_discover(args):
    LOGGER.info("Starting discovery.")

    config = load_config(args.config)
    state = load_state(args.state)

    auth_stub = get_auth_stub(config)

    catalog = []

    for available_stream_accessor in AVAILABLE_STREAM_ACCESSORS:
        stream_accessor = available_stream_accessor(
            config, state, auth_stub, None)

        catalog += stream_accessor.generate_catalog()

    print(json.dumps({'streams': catalog}))


def _is_selected(catalog_entry):
    default = catalog_entry.get('selected-by-default', False)

    return ((catalog_entry.get('inclusion') == 'automatic') or
            (catalog_entry.get('inclusion') == 'available' and
             catalog_entry.get('selected', default) is True))


def do_sync(args):
    LOGGER.info("Starting sync.")

    config = load_config(args.config)
    state = load_state(args.state)
    catalog = load_catalog(args.properties)

    auth_stub = get_auth_stub(config)

    stream_accessors = []

    subscriber_selected = False
    subscriber_catalog = None
    list_subscriber_selected = False

    for stream_catalog in catalog.get('streams'):
        stream_accessor = None

        if not _is_selected(stream_catalog.get('schema', {})):
            LOGGER.info("'{}' is not marked selected, skipping."
                        .format(stream_catalog.get('stream')))
            continue

        if SubscriberDataAccessObject.matches_catalog(stream_catalog):
            subscriber_selected = True
            subscriber_catalog = stream_catalog
            LOGGER.info("'subscriber' selected, will replicate via "
                        "'list_subscriber'")
            continue

        if ListSubscriberDataAccessObject.matches_catalog(stream_catalog):
            list_subscriber_selected = True

        for available_stream_accessor in AVAILABLE_STREAM_ACCESSORS:
            if available_stream_accessor.matches_catalog(stream_catalog):
                stream_accessors.append(available_stream_accessor(
                    config, state, auth_stub, stream_catalog))

                break

    if subscriber_selected and not list_subscriber_selected:
        LOGGER.fatal('Cannot replicate `subscriber` without '
                     '`list_subscriber`. Please select `list_subscriber` '
                     'and try again.')
        exit(1)

    for stream_accessor in stream_accessors:
        if isinstance(stream_accessor, ListSubscriberDataAccessObject) and \
           subscriber_selected:
            stream_accessor.replicate_subscriber = True
            stream_accessor.subscriber_catalog = subscriber_catalog

        try:
            stream_accessor.state = state
            stream_accessor.sync()
            state = stream_accessor.state

        except Exception:
            LOGGER.error('Failed to sync endpoint, moving on!')

    save_state(state)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-c', '--config', help='Config file', required=True)
    parser.add_argument(
        '-s', '--state', help='State file')
    parser.add_argument(
        '-p', '--properties', help='Catalog file with fields selected')

    parser.add_argument(
        '-d', '--discover',
        help='Build a catalog from the underlying schema',
        action='store_true')
    parser.add_argument(
        '-S', '--select-all',
        help=('When "--discover" is set, this flag selects all fields for '
              'replication in the generated catalog'),
        action='store_true')

    args = parser.parse_args()

    try:
        if args.discover:
            do_discover(args)
        elif args.properties:
            do_sync(args)
        else:
            LOGGER.info("No properties were selected")
    except RuntimeError as exception:
        LOGGER.error(str(exception))
        LOGGER.fatal("Run failed.")
        exit(1)


if __name__ == '__main__':
    main()
