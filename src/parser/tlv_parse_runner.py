"""Compatibility wrapper for the runtime pipeline entrypoint."""

try:
    from .runtime_pipeline import (
        CsvRunLogger,
        MMWaveSerialReader,
        ParsedFrame,
        ReaderStats,
        append_error_log,
        build_arg_parser,
        build_keepout_boxes,
        build_static_clutter_boxes,
        main,
        parse_args,
        run_realtime,
        send_config,
    )
except ImportError:
    from runtime_pipeline import (
        CsvRunLogger,
        MMWaveSerialReader,
        ParsedFrame,
        ReaderStats,
        append_error_log,
        build_arg_parser,
        build_keepout_boxes,
        build_static_clutter_boxes,
        main,
        parse_args,
        run_realtime,
        send_config,
    )


if __name__ == "__main__":
    main()
