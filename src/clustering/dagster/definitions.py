"""Dagster definitions module for the clustering pipeline."""

import os
from types import SimpleNamespace

import dagster as dg
import yaml

# Import all assets from the top-level assets module
from clustering.dagster.assets import (
    cluster_reassignment,
    external_assign_clusters,
    external_calculate_cluster_metrics,
    external_dimensionality_reduced_features,
    external_fe_raw_data,
    external_feature_metadata,
    # External preprocessing assets
    external_features_data,
    external_filtered_features,
    external_generate_cluster_visualizations,
    external_imputed_features,
    external_normalized_data,
    external_optimal_cluster_counts,
    external_outlier_removed_features,
    external_save_cluster_assignments,
    external_save_clustering_models,
    external_train_clustering_models,
    # Internal ML assets
    internal_assign_clusters,
    internal_calculate_cluster_metrics,
    internal_dimensionality_reduced_features,
    internal_fe_raw_data,
    internal_feature_metadata,
    internal_filtered_features,
    internal_generate_cluster_visualizations,
    internal_imputed_features,
    internal_normalized_data,
    # Internal preprocessing assets
    internal_normalized_sales_data,
    internal_optimal_cluster_counts,
    internal_outlier_removed_features,
    internal_output_sales_table,
    internal_product_category_mapping,
    internal_raw_sales_data,
    internal_sales_by_category,
    internal_sales_with_categories,
    internal_save_cluster_assignments,
    internal_save_clustering_models,
    internal_train_clustering_models,
    merged_cluster_assignments,
    merged_clusters,
    optimized_merged_clusters,
    preprocessed_external_data,
    save_merged_cluster_assignments,
)
from clustering.dagster.resources import data_io, logger_service

# Define essential jobs
# 1. Internal preprocessing job
internal_preprocessing_job = dg.define_asset_job(
    name="internal_preprocessing_job",
    selection=[
        internal_raw_sales_data,
        internal_product_category_mapping,
        internal_sales_with_categories,
        internal_normalized_sales_data,
        internal_sales_by_category,
        internal_output_sales_table,
    ],
    tags={"kind": "internal_preprocessing"},
)

# 2. External preprocessing job
external_preprocessing_job = dg.define_asset_job(
    name="external_preprocessing_job",
    selection=[
        external_features_data,
        preprocessed_external_data,
    ],
    tags={"kind": "external_preprocessing"},
)

# 3. Internal ML job
internal_ml_job = dg.define_asset_job(
    name="internal_ml_job",
    selection=[
        # Feature engineering assets
        internal_fe_raw_data,
        internal_filtered_features,
        internal_imputed_features,
        internal_normalized_data,
        internal_outlier_removed_features,
        internal_dimensionality_reduced_features,
        internal_feature_metadata,
        # Model training assets
        internal_optimal_cluster_counts,
        internal_train_clustering_models,
        internal_save_clustering_models,
        # Cluster assignment
        internal_assign_clusters,
        internal_save_cluster_assignments,
        # Cluster analysis
        internal_calculate_cluster_metrics,
        internal_generate_cluster_visualizations,
    ],
    tags={"kind": "internal_ml"},
)

# 4. External ML job
external_ml_job = dg.define_asset_job(
    name="external_ml_job",
    selection=[
        # Feature engineering assets
        external_fe_raw_data,
        external_filtered_features,
        external_imputed_features,
        external_normalized_data,
        external_outlier_removed_features,
        external_dimensionality_reduced_features,
        external_feature_metadata,
        # Model training assets
        external_optimal_cluster_counts,
        external_train_clustering_models,
        external_save_clustering_models,
        # Cluster assignment
        external_assign_clusters,
        external_save_cluster_assignments,
        # Cluster analysis
        external_calculate_cluster_metrics,
        external_generate_cluster_visualizations,
    ],
    tags={"kind": "external_ml"},
)

# 5. Full pipeline job (combining all internal and external)
full_pipeline_job = dg.define_asset_job(
    name="full_pipeline_job",
    selection=[
        # Internal preprocessing
        internal_raw_sales_data,
        internal_product_category_mapping,
        internal_sales_with_categories,
        internal_normalized_sales_data,
        internal_sales_by_category,
        internal_output_sales_table,
        # Internal feature engineering
        internal_fe_raw_data,
        internal_filtered_features,
        internal_imputed_features,
        internal_normalized_data,
        internal_outlier_removed_features,
        internal_dimensionality_reduced_features,
        internal_feature_metadata,
        # Internal model training
        internal_optimal_cluster_counts,
        internal_train_clustering_models,
        internal_save_clustering_models,
        # Internal cluster assignment
        internal_assign_clusters,
        internal_save_cluster_assignments,
        # Internal cluster analysis
        internal_calculate_cluster_metrics,
        internal_generate_cluster_visualizations,
        # External preprocessing
        external_features_data,
        preprocessed_external_data,
        # External feature engineering
        external_fe_raw_data,
        external_filtered_features,
        external_imputed_features,
        external_normalized_data,
        external_outlier_removed_features,
        external_dimensionality_reduced_features,
        external_feature_metadata,
        # External model training
        external_optimal_cluster_counts,
        external_train_clustering_models,
        external_save_clustering_models,
        # External cluster assignment
        external_assign_clusters,
        external_save_cluster_assignments,
        # External cluster analysis
        external_calculate_cluster_metrics,
        external_generate_cluster_visualizations,
        # Merging
        merged_clusters,
        merged_cluster_assignments,
        optimized_merged_clusters,
        cluster_reassignment,
        save_merged_cluster_assignments,
    ],
    tags={"kind": "complete_pipeline"},
)

# 6. Merging job (combining internal and external clusters)
merging_job = dg.define_asset_job(
    name="merging_job",
    selection=[
        # Merging assets
        merged_clusters,
        merged_cluster_assignments,
        optimized_merged_clusters,
        cluster_reassignment,
        save_merged_cluster_assignments,
    ],
    tags={"kind": "merging"},
)


# Define resources with a simple, direct approach
def get_resources_by_env(env: str = "dev") -> dict[str, dg.ResourceDefinition]:
    """Get resource definitions based on environment.

    Args:
        env: Environment name (dev, staging, prod)

    Returns:
        Dictionary of resource definitions
    """
    # Load configuration directly
    config_path = os.path.join(os.path.dirname(__file__), "resources", "configs", f"{env}.yml")
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    # Extract job parameters
    job_params = config_data.get("job_params", {})

    # Create config object directly
    params = SimpleNamespace(**job_params)
    params.env = env  # Add environment name

    # Extract other resource configurations
    logger_config = config_data.get("logger", {})
    readers_config = config_data.get("readers", {})
    writers_config = config_data.get("writers", {})

    # Create the params resource once
    params_resource = dg.resource(lambda: params)()

    # Create all resources in a flat structure
    resources = {
        # Core resources
        "io_manager": dg.FilesystemIOManager(base_dir="storage"),
        # Use the same params resource for both job_params and config
        # Some assets look for "job_params" while others look for "config"
        "job_params": params_resource,
        "config": params_resource,
        # Logger
        "logger": logger_service.configured(
            {
                "sink": logger_config.get("sink", f"logs/dagster_{env}.log"),
                "level": logger_config.get("level", "INFO"),
            }
        ),
        # Data readers
        "internal_ns_sales": data_io.data_reader.configured(
            readers_config.get("internal_ns_sales", {})
        ),
        "internal_ns_map": data_io.data_reader.configured(
            readers_config.get("internal_ns_map", {})
        ),
        # Feature engineering reader
        "output_sales_reader": data_io.data_reader.configured(
            readers_config.get("output_sales", {})
        ),
        # External data readers
        "external_data_reader": data_io.data_reader.configured(
            readers_config.get("external_data_source", {})
        ),
        "input_external_placerai_reader": data_io.data_reader.configured(
            readers_config.get("external_placerai", {})
        ),
        # Data writers
        "output_sales_writer": data_io.data_writer.configured(
            writers_config.get("internal_sales_output", {})
        ),
        "output_sales_percent_writer": data_io.data_writer.configured(
            writers_config.get("internal_sales_percent_output", {})
        ),
        "output_clusters_writer": data_io.data_writer.configured(
            writers_config.get("internal_clusters_output", {})
        ),
        # External data writers
        "output_external_data_writer": data_io.data_writer.configured(
            writers_config.get("external_data_output", {})
        ),
        # Model output writer
        "internal_model_output": data_io.data_writer.configured(
            writers_config.get("model_output", {})
        ),
        # Cluster assignments writer
        "internal_cluster_assignments": data_io.data_writer.configured(
            writers_config.get("cluster_assignments", {})
        ),
        # External model output writer
        "external_model_output": data_io.data_writer.configured(
            writers_config.get("external_model_output", {})
        ),
        # External cluster assignments writer
        "external_cluster_assignments": data_io.data_writer.configured(
            writers_config.get("external_cluster_assignments", {})
        ),
        # Merged cluster assignments writer
        "merged_cluster_assignments": data_io.data_writer.configured(
            writers_config.get("merged_cluster_assignments", {})
        ),
    }

    return resources


# Create definitions
def create_definitions(env: str = "dev") -> dg.Definitions:
    """Create Dagster definitions.

    Args:
        env: Environment name (dev, staging, prod)

    Returns:
        Dagster definitions
    """
    resources = get_resources_by_env(env)

    # Include all assets in one place
    assets = [
        # Preprocessing assets - Internal
        internal_raw_sales_data,
        internal_product_category_mapping,
        internal_sales_with_categories,
        internal_normalized_sales_data,
        internal_sales_by_category,
        internal_output_sales_table,
        # Preprocessing assets - External
        external_features_data,
        preprocessed_external_data,
        # Feature engineering assets - Internal
        internal_fe_raw_data,
        internal_filtered_features,
        internal_imputed_features,
        internal_normalized_data,
        internal_outlier_removed_features,
        internal_dimensionality_reduced_features,
        internal_feature_metadata,
        # Feature engineering assets - External
        external_fe_raw_data,
        external_filtered_features,
        external_imputed_features,
        external_normalized_data,
        external_outlier_removed_features,
        external_dimensionality_reduced_features,
        external_feature_metadata,
        # Model training - Internal
        internal_optimal_cluster_counts,
        internal_train_clustering_models,
        internal_save_clustering_models,
        # Model training - External
        external_optimal_cluster_counts,
        external_train_clustering_models,
        external_save_clustering_models,
        # Cluster assignment - Internal
        internal_assign_clusters,
        internal_save_cluster_assignments,
        # Cluster assignment - External
        external_assign_clusters,
        external_save_cluster_assignments,
        # Cluster analysis - Internal
        internal_calculate_cluster_metrics,
        internal_generate_cluster_visualizations,
        # Cluster analysis - External
        external_calculate_cluster_metrics,
        external_generate_cluster_visualizations,
        # Merging assets
        merged_clusters,
        merged_cluster_assignments,
        optimized_merged_clusters,
        cluster_reassignment,
        save_merged_cluster_assignments,
    ]

    # Create and return definitions with all jobs
    return dg.Definitions(
        assets=assets,
        resources=resources,
        jobs=[
            internal_preprocessing_job,
            external_preprocessing_job,
            internal_ml_job,
            external_ml_job,
            full_pipeline_job,
            merging_job,
        ],        
    )


# Create default definitions with dev environment
defs = create_definitions(env="dev")