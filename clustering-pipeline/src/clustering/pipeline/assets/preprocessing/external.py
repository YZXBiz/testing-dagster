"""External preprocessing assets for the clustering pipeline."""

import dagster as dg
import polars as pl


@dg.asset(
    io_manager_key="io_manager",
    compute_kind="external_preprocessing",
    group_name="preprocessing",
    required_resource_keys={
        "input_external_placerai_reader",
        "input_external_urbanicity_template_reader",
        "input_external_urbanicity_experiment_reader",
    },
)
def external_features_data(
    context: dg.AssetExecutionContext,
) -> pl.DataFrame:
    """Load and merge external feature data.

    Args:
        context: Asset execution context

    Returns:
        DataFrame containing merged external data
    """
    # Step 1: Gather all external data readers
    context.log.info("Initializing external data readers")
    external_readers = [
        context.resources.input_external_placerai_reader,
        context.resources.input_external_urbanicity_template_reader,
        context.resources.input_external_urbanicity_experiment_reader,
        # Add additional readers here as needed
    ]

    # Step 2: Read data from all sources
    context.log.info("Reading data from all external sources")
    dataframes: list[pl.DataFrame] = []

    for reader in external_readers:
        context.log.info(f"Reading from: {reader}")
        df = reader.read()

        # Validate we have the key column needed for merging
        if "STORE_NBR" not in df.columns:
            context.log.warning(f"Missing STORE_NBR column in data from {reader}. Skipping.")
            continue

        dataframes.append(df)

    # Step 3: Handle the single or empty dataframe case
    if len(dataframes) == 0:
        context.log.error("No valid external data sources found")
        raise ValueError("Failed to read any valid external data")

    if len(dataframes) == 1:
        context.log.info("Only one external data source. No merging needed.")
        return dataframes[0]

    # Start with the first dataframe
    context.log.info(
        f"Merging {len(dataframes)} external data sources with outer join on STORE_NBR"
    )
    base_df = dataframes[0]

    # Join with each subsequent dataframe using coalesce=True to avoid duplicate STORE_NBR columns
    for i, df in enumerate(dataframes[1:], 1):
        context.log.info(f"Joining with data source {i + 1} with coalesced join key")
        base_df = base_df.join(df, on="STORE_NBR", how="outer", coalesce=True)

    context.log.info(
        f"Merged external data has {base_df.shape[0]} rows and {base_df.shape[1]} columns"
    )
    return base_df


@dg.asset(
    io_manager_key="io_manager",
    deps=["external_features_data"],
    compute_kind="external_preprocessing",
    group_name="preprocessing",
    required_resource_keys={"output_external_data_writer"},
)
def preprocessed_external_data(
    context: dg.AssetExecutionContext,
    external_features_data: pl.DataFrame,
) -> pl.DataFrame:
    """Process external data and save the results.

    Args:
        context: Asset execution context
        external_features_data: External features data

    Returns:
        Processed external data
    """
    context.log.info("Processing external data")

    # Apply any necessary preprocessing steps here
    # For now, we'll just use the data as is
    processed_data = external_features_data

    # Save the processed data
    context.log.info("Saving preprocessed external data")
    output_data_writer = context.resources.output_external_data_writer
    output_data_writer.write(data=processed_data)

    # Return the data so it can be used by downstream assets
    return processed_data
