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
        build_runtime_processing_context,
        build_static_clutter_boxes,
        main,
        parse_args,
        process_runtime_frame,
        run_realtime,
        send_config,
        transform_points_to_world,
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
        build_runtime_processing_context,
        build_static_clutter_boxes,
        main,
        parse_args,
        process_runtime_frame,
        run_realtime,
        send_config,
        transform_points_to_world,
    )


rotate_points_xy = transform_points_to_world


if __name__ == "__main__":
    main()
