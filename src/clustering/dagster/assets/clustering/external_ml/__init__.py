"""External data clustering ML assets for the Dagster pipeline."""

# Export the feature engineering assets
from clustering.dagster.assets.clustering.external_ml.feature_engineering import (
    external_dimensionality_reduced_features,
    external_fe_raw_data,
    external_feature_metadata,
    external_filtered_features,
    external_imputed_features,
    external_normalized_data,
    external_outlier_removed_features,
)

# Export the model training and prediction assets
from clustering.dagster.assets.clustering.external_ml.model_training import (
    external_assign_clusters,
    external_calculate_cluster_metrics,
    external_generate_cluster_visualizations,
    external_optimal_cluster_counts,
    external_save_cluster_assignments,
    external_save_clustering_models,
    external_train_clustering_models,
)

__all__ = [
    # Feature engineering
    "external_fe_raw_data",
    "external_filtered_features",
    "external_imputed_features",
    "external_normalized_data",
    "external_outlier_removed_features",
    "external_dimensionality_reduced_features",
    "external_feature_metadata",
    # Model training
    "external_optimal_cluster_counts",
    "external_train_clustering_models",
    "external_save_clustering_models",
    # Cluster prediction
    "external_assign_clusters",
    "external_save_cluster_assignments",
    # Model evaluation
    "external_calculate_cluster_metrics",
    "external_generate_cluster_visualizations",
]
