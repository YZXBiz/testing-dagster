"""Dagster assets for the clustering pipeline."""

# Preprocessing assets
# Feature engineering, model training, cluster assignment and analysis assets
from .clustering import (
    external_assign_clusters,
    external_dimensionality_reduced_features,
    external_fe_raw_data,
    external_filtered_features,
    external_imputed_features,
    external_normalized_data,
    external_optimal_cluster_counts,
    external_outlier_removed_features,
    external_save_cluster_assignments,
    external_save_clustering_models,
    external_train_clustering_models,
    internal_assign_clusters,
    internal_dimensionality_reduced_features,
    internal_fe_raw_data,
    internal_filtered_features,
    internal_imputed_features,
    internal_normalized_data,
    internal_optimal_cluster_counts,
    internal_outlier_removed_features,
    internal_save_cluster_assignments,
    internal_save_clustering_models,
    internal_train_clustering_models,
)

# Import merging assets
from .merging.merge import (
    cluster_reassignment,
    merged_cluster_assignments,
    merged_clusters,
    optimized_merged_clusters,
    save_merged_cluster_assignments,
)

# Import preprocessing external assets if needed
from .preprocessing.external import (
    external_features_data,
    preprocessed_external_data,
)

# Preprocessing assets
from .preprocessing.internal import (
    internal_normalized_sales_data,
    internal_output_sales_table,
    internal_product_category_mapping,
    internal_raw_sales_data,
    internal_sales_by_category,
    internal_sales_with_categories,
)

__all__ = [
    # Preprocessing - internal
    "internal_raw_sales_data",
    "internal_product_category_mapping",
    "internal_sales_with_categories",
    "internal_sales_by_category",
    "internal_output_sales_table",
    "internal_normalized_sales_data",
    # Preprocessing - external
    "external_features_data",
    "preprocessed_external_data",
    # Feature engineering - Internal
    "internal_fe_raw_data",
    "internal_filtered_features",
    "internal_imputed_features",
    "internal_normalized_data",
    "internal_outlier_removed_features",
    "internal_dimensionality_reduced_features",
    # Feature engineering - External
    "external_fe_raw_data",
    "external_filtered_features",
    "external_imputed_features",
    "external_normalized_data",
    "external_outlier_removed_features",
    "external_dimensionality_reduced_features",
    # Model training - Internal
    "internal_optimal_cluster_counts",
    "internal_train_clustering_models",
    "internal_save_clustering_models",
    # Model training - External
    "external_optimal_cluster_counts",
    "external_train_clustering_models",
    "external_save_clustering_models",
    # Cluster assignment - Internal
    "internal_assign_clusters",
    "internal_save_cluster_assignments",
    # Cluster assignment - External
    "external_assign_clusters",
    "external_save_cluster_assignments",
    # Merging assets
    "merged_clusters",
    "merged_cluster_assignments",
    "optimized_merged_clusters",
    "cluster_reassignment",
    "save_merged_cluster_assignments",
]
