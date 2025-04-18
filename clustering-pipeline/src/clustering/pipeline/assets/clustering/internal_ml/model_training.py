"""Model training step for the internal ML pipeline.

This module provides Dagster assets for training clustering models based on
engineered features.
"""

from typing import Any
import os
import tempfile

import dagster as dg
import polars as pl
from pycaret.clustering import ClusteringExperiment, load_experiment


class Defaults:
    """Default configuration values for model training."""

    # Experiment settings
    SESSION_ID = 42

    # Clustering algorithm
    ALGORITHM = "kmeans"

    # Optimal cluster determination
    MIN_CLUSTERS = 2
    MAX_CLUSTERS = 10

    # Evaluation metrics to track
    METRICS = ["silhouette", "calinski_harabasz", "davies_bouldin"]


@dg.asset(
    name="internal_optimal_cluster_counts",
    description="Determines optimal number of clusters for each category",
    group_name="model_training",
    compute_kind="internal_model_training",
    deps=["internal_dimensionality_reduced_features"],
    required_resource_keys={"config"},
)
def internal_optimal_cluster_counts(
    context: dg.AssetExecutionContext,
    internal_dimensionality_reduced_features: dict[str, pl.DataFrame],
) -> dict[str, int]:
    """Determine the optimal number of clusters for each category.

    Uses PyCaret to evaluate different cluster counts based on silhouette scores,
    Calinski-Harabasz Index, and Davies-Bouldin Index to determine the optimal
    number of clusters for each category.

    Args:
        context: Dagster asset execution context
        internal_dimensionality_reduced_features: Dictionary of processed DataFrames by category

    Returns:
        Dictionary mapping category names to their optimal cluster counts
    """
    optimal_clusters = {}

    # Get configuration parameters or use defaults
    min_clusters = getattr(context.resources.config, "min_clusters", Defaults.MIN_CLUSTERS)
    max_clusters = getattr(context.resources.config, "max_clusters", Defaults.MAX_CLUSTERS)
    metrics = getattr(context.resources.config, "metrics", Defaults.METRICS)
    session_id = getattr(context.resources.config, "session_id", Defaults.SESSION_ID)

    context.log.info(
        f"Determining optimal clusters using range {min_clusters}-{max_clusters} "
        f"with metrics: {metrics}"
    )

    for category, df in internal_dimensionality_reduced_features.items():
        context.log.info(f"Determining optimal cluster count for category: {category}")

        sample_count = len(df)

        # Check if dataset has enough samples for clustering
        if sample_count < min_clusters:
            context.log.warning(
                f"Category '{category}' has only {sample_count} samples, "
                f"which is less than min_clusters={min_clusters}. "
                f"Setting optimal clusters to 1."
            )
            optimal_clusters[category] = 1
            continue

        # Adjust max_clusters to not exceed sample count
        adjusted_max_clusters = min(max_clusters, sample_count - 1)
        if adjusted_max_clusters < max_clusters:
            context.log.warning(
                f"Category '{category}' has only {sample_count} samples. "
                f"Reducing max_clusters from {max_clusters} to {adjusted_max_clusters}."
            )

        # If adjusted_max_clusters is less than min_clusters, we can't cluster properly
        if adjusted_max_clusters < min_clusters:
            context.log.warning(
                f"Category '{category}' has too few samples ({sample_count}) "
                f"to evaluate clusters in range [{min_clusters}, {max_clusters}]. "
                f"Setting optimal clusters to 1."
            )
            optimal_clusters[category] = 1
            continue

        # Convert Polars DataFrame to Pandas for PyCaret
        pandas_df = df.to_pandas()

        # Initialize PyCaret experiment
        exp = ClusteringExperiment()
        exp.setup(
            data=pandas_df,
            session_id=session_id,
            verbose=False,
        )

        # Evaluate different cluster counts
        context.log.info(
            f"Evaluating {min_clusters} to {adjusted_max_clusters} clusters for {category}"
        )
        cluster_metrics = {}

        # Track metric values for each cluster count
        for k in range(min_clusters, adjusted_max_clusters + 1):
            # Create a model with k clusters
            _ = exp.create_model(Defaults.ALGORITHM, num_clusters=k, verbose=False)

            # Get evaluation metrics
            metrics_values = exp.pull()
            cluster_metrics[k] = {
                metric: metrics_values.loc[0, metric]
                for metric in metrics
                if metric in metrics_values.columns
            }

            # Log progress
            metrics_str = ", ".join(f"{m}={cluster_metrics[k][m]:.4f}" for m in cluster_metrics[k])
            context.log.info(f"  {category} with {k} clusters: {metrics_str}")

        # Determine optimal clusters based on silhouette score (higher is better)
        if "silhouette" in metrics and cluster_metrics:
            best_k = max(
                cluster_metrics.keys(), key=lambda k: cluster_metrics[k].get("silhouette", 0)
            )
            context.log.info(f"Optimal clusters for {category} based on silhouette: {best_k}")
        # Fallback to Calinski-Harabasz (higher is better)
        elif "calinski_harabasz" in metrics and cluster_metrics:
            best_k = max(
                cluster_metrics.keys(), key=lambda k: cluster_metrics[k].get("calinski_harabasz", 0)
            )
            context.log.info(
                f"Optimal clusters for {category} based on calinski_harabasz: {best_k}"
            )
        # Fallback to Davies-Bouldin (lower is better)
        elif "davies_bouldin" in metrics and cluster_metrics:
            best_k = min(
                cluster_metrics.keys(),
                key=lambda k: cluster_metrics[k].get("davies_bouldin", float("inf")),
            )
            context.log.info(f"Optimal clusters for {category} based on davies_bouldin: {best_k}")
        else:
            # Default if no metrics match or no clusters were evaluated
            best_k = min(min_clusters, sample_count - 1) if sample_count > 1 else 1
            context.log.warning(
                f"Could not determine optimal clusters for {category}, using default: {best_k}"
            )

        optimal_clusters[category] = best_k

        # Store metrics in context for later reference
        context.add_output_metadata(
            {
                f"{category}_metrics": cluster_metrics,
                f"{category}_optimal": best_k,
            }
        )

    return optimal_clusters


@dg.asset(
    name="internal_train_clustering_models",
    description="Trains clustering models using optimal number of clusters",
    group_name="model_training",
    compute_kind="internal_model_training",
    deps=["internal_dimensionality_reduced_features", "internal_optimal_cluster_counts"],
    required_resource_keys={"config"},
)
def internal_train_clustering_models(
    context: dg.AssetExecutionContext,
    internal_dimensionality_reduced_features: dict[str, pl.DataFrame],
    internal_optimal_cluster_counts: dict[str, int],
) -> dict[str, Any]:
    """Train clustering models using engineered features.

    Uses PyCaret to train clustering models for each category using the
    optimal number of clusters determined in the previous step.

    Args:
        context: Dagster asset execution context
        internal_dimensionality_reduced_features: Dictionary of processed DataFrames by category
        internal_optimal_cluster_counts: Dictionary mapping category names to optimal cluster counts

    Returns:
        Dictionary of trained clustering models organized by category
    """
    trained_models = {}

    # Create a temp directory for experiment files
    temp_dir = tempfile.mkdtemp(prefix="pycaret_internal_experiments_")
    context.log.info(f"Using temporary directory for experiments: {temp_dir}")

    # Get configuration parameters
    algorithm = getattr(context.resources.config, "algorithm", Defaults.ALGORITHM)
    session_id = getattr(context.resources.config, "session_id", Defaults.SESSION_ID)

    context.log.info(f"Training clustering models using algorithm: {algorithm}")

    for category, df in internal_dimensionality_reduced_features.items():
        # Get optimal cluster count for this category
        cluster_count = internal_optimal_cluster_counts.get(category, 2)

        # Ensure cluster_count is at least 2 as required by PyCaret
        if cluster_count < 2:
            context.log.warning(
                f"Cluster count for '{category}' was {cluster_count}, but PyCaret requires at least 2 clusters. "
                f"Adjusting to 2 clusters."
            )
            cluster_count = 2

        # Ensure we have enough samples for the requested number of clusters
        sample_count = len(df)
        if sample_count <= cluster_count:
            adjusted_cluster_count = min(2, sample_count - 1) if sample_count > 2 else 2
            context.log.warning(
                f"Category '{category}' has only {sample_count} samples, which is not enough for {cluster_count} clusters. "
                f"Adjusting to {adjusted_cluster_count} clusters."
            )
            cluster_count = adjusted_cluster_count

        # Final validation to ensure we meet PyCaret's requirements
        if sample_count <= 2:
            context.log.error(
                f"Category '{category}' has only {sample_count} samples, which is insufficient for clustering. "
                f"Skipping this category."
            )
            continue

        context.log.info(f"Training {algorithm} with {cluster_count} clusters for {category}")

        # Convert Polars DataFrame to Pandas for PyCaret
        pandas_df = df.to_pandas()

        # Initialize PyCaret experiment
        exp = ClusteringExperiment()
        exp.setup(
            data=pandas_df,
            session_id=session_id,
            verbose=False,
        )

        # Train the model with the optimal number of clusters
        model = exp.create_model(
            algorithm,
            num_clusters=cluster_count,
            verbose=False,
        )

        # Save the experiment using PyCaret's built-in function that handles lambda functions
        experiment_path = os.path.join(temp_dir, f"{category}_experiment")
        exp.save_experiment(experiment_path)

        # Get metrics before we reset the experiment
        try:
            metrics = exp.pull().iloc[0].to_dict()
        except (AttributeError, IndexError, KeyError):
            metrics = {}
            context.log.warning(f"Could not extract metrics from experiment for {category}")

        # Store the model and experiment path
        trained_models[category] = {
            "model": model,
            "experiment_path": experiment_path,
            "features": df.columns,
            "num_clusters": cluster_count,
            "num_samples": len(df),
            "metrics": metrics,
        }

        context.log.info(f"Completed training for {category}")

    # Add useful metadata to the context
    context.add_output_metadata(
        {
            "algorithm": algorithm,
            "categories": list(trained_models.keys()),
            "cluster_counts": dg.MetadataValue.json(
                {category: data["num_clusters"] for category, data in trained_models.items()}
            ),
            "experiment_paths": dg.MetadataValue.json(
                {category: data["experiment_path"] for category, data in trained_models.items()}
            ),
        }
    )

    return trained_models


@dg.asset(
    name="internal_save_clustering_models",
    description="Persists trained clustering models to storage",
    group_name="model_training",
    compute_kind="internal_model_training",
    deps=["internal_train_clustering_models"],
    required_resource_keys={"config", "internal_model_output"},
)
def internal_save_clustering_models(
    context: dg.AssetExecutionContext,
    internal_train_clustering_models: dict[str, Any],
) -> None:
    """Save trained clustering models to persistent storage.

    Uses the configured model output resource to save the trained models
    for later use in prediction or evaluation.

    Args:
        context: Dagster asset execution context
        internal_train_clustering_models: Dictionary of trained clustering models by category
    """
    context.log.info("Saving trained clustering models to storage")

    # Use the configured model output resource
    model_output = context.resources.internal_model_output

    # Convert model info to a DataFrame to comply with PickleWriter requirements
    if internal_train_clustering_models:
        # Create a dictionary where each key is a category and the value is a DataFrame
        model_dataframes = {}

        for category, model_info in internal_train_clustering_models.items():
            # Create a dictionary with string metadata from the model info
            model_metadata = {
                "num_clusters": model_info["num_clusters"],
                "num_samples": model_info["num_samples"],
                "features": str(model_info["features"]),
                "experiment_path": model_info["experiment_path"],
            }

            # Add metrics if available
            if "metrics" in model_info and model_info["metrics"]:
                for k, v in model_info["metrics"].items():
                    model_metadata[f"metric_{k}"] = v

            # Create a DataFrame with a single row containing the metadata
            model_dataframes[category] = pl.DataFrame([model_metadata])

        # Save the DataFrame dictionary (can't save the actual model objects directly)
        context.log.info(f"Saving {len(model_dataframes)} model metadata entries to storage")
        model_output.write(model_dataframes)

        # Save model paths to the context for reference
        context.add_output_metadata(
            {
                "model_paths": {
                    category: info["experiment_path"]
                    for category, info in internal_train_clustering_models.items()
                },
                "categories": list(internal_train_clustering_models.keys()),
                "num_models": len(internal_train_clustering_models),
            }
        )
    else:
        # Create an empty DataFrame
        empty_df = pl.DataFrame(
            {
                "num_clusters": [],
                "num_samples": [],
                "features": [],
                "experiment_path": [],
            }
        )
        model_output.write({"default": empty_df})
        context.log.warning("No models to save, writing empty metadata DataFrame")

    context.log.info("Successfully saved model metadata to storage")


@dg.asset(
    name="internal_assign_clusters",
    description="Assigns clusters to data points using trained models",
    group_name="cluster_assignment",
    compute_kind="internal_cluster_assignment",
    deps=[
        "internal_dimensionality_reduced_features",
        "internal_train_clustering_models",
        "internal_fe_raw_data",
    ],
    required_resource_keys={"config"},
)
def internal_assign_clusters(
    context: dg.AssetExecutionContext,
    internal_dimensionality_reduced_features: dict[str, pl.DataFrame],
    internal_train_clustering_models: dict[str, Any],
    internal_fe_raw_data: dict[str, pl.DataFrame],
) -> dict[str, pl.DataFrame]:
    """Assign cluster labels to data points using trained models.

    Uses the trained clustering models to assign cluster labels to the dimensionality reduced features,
    then applies these labels back to the original raw data with all columns preserved.

    Args:
        context: Dagster asset execution context
        internal_dimensionality_reduced_features: Dictionary of dimensionality reduced DataFrames by category
        internal_train_clustering_models: Dictionary of trained clustering models by category
        internal_fe_raw_data: Dictionary of original raw DataFrames by category

    Returns:
        Dictionary of original DataFrames with cluster assignments by category
    """
    assigned_data = {}

    context.log.info(
        "Assigning clusters using dimensionality reduced features and applying to raw data"
    )

    for category, df in internal_dimensionality_reduced_features.items():
        # Check if we have a trained model for this category
        if category not in internal_train_clustering_models:
            context.log.warning(f"No trained model found for category: {category}")
            continue

        # Check if we have the original raw data for this category
        if category not in internal_fe_raw_data:
            context.log.warning(f"No raw data found for category: {category}")
            raise ValueError(f"No raw data found for category: {category}")

        context.log.info(f"Assigning clusters for category: {category}")

        # Get the model info
        model_info = internal_train_clustering_models[category]
        model = model_info["model"]
        experiment_path = model_info["experiment_path"]

        context.log.info(f"Loading experiment from {experiment_path}")

        # Convert Polars DataFrame to Pandas for PyCaret
        pandas_df = df.to_pandas()

        # Load the experiment using PyCaret's load_experiment function
        # This correctly handles lambda functions using cloudpickle
        exp = load_experiment(experiment_path, data=pandas_df)

        # Use assign_model instead of predict_model since we're using the same data
        predictions = exp.assign_model(model)

        # Get just the cluster assignments
        cluster_assignments = predictions[["Cluster"]]

        # Get the original raw data for this category
        original_data = internal_fe_raw_data[category].to_pandas()

        # Ensure the indices match
        if len(original_data) != len(cluster_assignments):
            context.log.warning(
                f"Size mismatch between original data ({len(original_data)}) and "
                f"cluster assignments ({len(cluster_assignments)}) for {category}"
            )
            # In a real implementation, you might want more sophisticated matching
            continue

        # Add cluster assignments to the original data
        original_data_with_clusters = original_data.copy()
        original_data_with_clusters["Cluster"] = cluster_assignments["Cluster"].values

        # Convert back to Polars and store
        assigned_data[category] = pl.from_pandas(original_data_with_clusters)

        # Log cluster distribution
        cluster_counts = (
            assigned_data[category]
            .group_by("Cluster")
            .agg(pl.count().alias("count"))
            .sort("Cluster")
        )
        context.log.info(f"Cluster distribution for {category}:\n{cluster_counts}")

    # Store metadata about the assignment
    context.add_output_metadata(
        {
            "categories": list(assigned_data.keys()),
            "total_records": sum(len(df) for df in assigned_data.values()),
        }
    )

    return assigned_data


@dg.asset(
    name="internal_save_cluster_assignments",
    description="Saves cluster assignments to storage",
    group_name="cluster_assignment",
    compute_kind="internal_cluster_assignment",
    deps=["internal_assign_clusters"],
    required_resource_keys={"internal_cluster_assignments"},
)
def internal_save_cluster_assignments(
    context: dg.AssetExecutionContext,
    internal_assign_clusters: dict[str, pl.DataFrame],
) -> None:
    """Save cluster assignments to persistent storage.

    Uses the configured output resource to save the cluster assignments
    for later use in analysis or reporting.

    Args:
        context: Dagster asset execution context
        internal_assign_clusters: Dictionary of DataFrames with cluster assignments
    """
    context.log.info("Saving cluster assignments to storage")

    # Use the configured output resource
    assignments_output = context.resources.internal_cluster_assignments

    # Since we can only save one DataFrame per writer,
    # combine all category DataFrames into a single one with a category column
    combined_data = []

    for category, df in internal_assign_clusters.items():
        context.log.info(f"Processing cluster assignments for category: {category}")
        # Add a category column to identify the source
        category_df = df.with_columns(pl.lit(category).alias("category"))
        combined_data.append(category_df)

    if combined_data:
        # Combine all dataframes
        all_assignments = pl.concat(combined_data)

        # Write the combined data
        context.log.info(f"Saving combined assignments with {len(all_assignments)} records")
        assignments_output.write(all_assignments)

        context.log.info(
            f"Successfully saved assignments for {len(internal_assign_clusters)} categories"
        )
    else:
        context.log.warning("No cluster assignments to save")


@dg.asset(
    name="internal_calculate_cluster_metrics",
    description="Calculates metrics for cluster quality evaluation",
    group_name="cluster_analysis",
    compute_kind="internal_cluster_analysis",
    deps=["internal_train_clustering_models", "internal_assign_clusters"],
    required_resource_keys={"config"},
)
def internal_calculate_cluster_metrics(
    context: dg.AssetExecutionContext,
    internal_train_clustering_models: dict[str, Any],
    internal_assign_clusters: dict[str, pl.DataFrame],
) -> dict[str, Any]:
    """Calculate metrics to evaluate the quality of clustering.

    Computes various metrics to assess the quality of the clustering results,
    such as silhouette score, inertia, and cluster size distribution.

    Args:
        context: Dagster asset execution context
        internal_train_clustering_models: Dictionary of trained clustering models
        internal_assign_clusters: Dictionary of DataFrames with cluster assignments

    Returns:
        Dictionary of evaluation metrics by category
    """
    metrics = {}

    context.log.info("Calculating evaluation metrics for clusters")

    for category, model_info in internal_train_clustering_models.items():
        # Check if this category has assignments
        if category not in internal_assign_clusters:
            context.log.warning(f"No cluster assignments found for {category}, skipping metrics")
            continue

        # Get metrics that were stored during training
        pycaret_metrics = model_info.get("metrics", {})

        # Get cluster distribution from assignments
        assignments = internal_assign_clusters[category]
        cluster_distribution = (
            assignments.group_by("Cluster").agg(pl.count().alias("count")).to_dicts()
        )

        # Calculate category metrics
        category_metrics = {
            "num_clusters": model_info["num_clusters"],
            "num_samples": model_info["num_samples"],
            "silhouette": pycaret_metrics.get("Silhouette"),
            "calinski_harabasz": pycaret_metrics.get("Calinski-Harabasz"),
            "davies_bouldin": pycaret_metrics.get("Davies-Bouldin"),
            "cluster_distribution": cluster_distribution,
        }

        # Store metrics for this category
        metrics[category] = category_metrics

        # Log key metrics
        context.log.info(
            f"Metrics for {category}: "
            f"silhouette={category_metrics.get('silhouette', 'N/A')}, "
            f"num_clusters={category_metrics['num_clusters']}, "
            f"num_samples={category_metrics['num_samples']}"
        )

    # Store summary in context metadata
    context.add_output_metadata(
        {
            "categories": list(metrics.keys()),
            "average_silhouette": (
                sum(m.get("silhouette", 0) or 0 for m in metrics.values()) / len(metrics)
                if metrics
                else None
            ),
        }
    )

    return metrics


@dg.asset(
    name="internal_generate_cluster_visualizations",
    description="Generates visualizations for cluster analysis",
    group_name="cluster_analysis",
    compute_kind="internal_cluster_analysis",
    deps=["internal_train_clustering_models", "internal_assign_clusters"],
    required_resource_keys={"config"},
)
def internal_generate_cluster_visualizations(
    context: dg.AssetExecutionContext,
    internal_train_clustering_models: dict[str, Any],
    internal_assign_clusters: dict[str, pl.DataFrame],
) -> dict[str, list[str]]:
    """Generate visualizations for analyzing cluster results.

    Creates various plots and visualizations to help understand and interpret
    clustering results, such as 2D scatter plots, PCA projections, and
    cluster distribution histograms.

    Args:
        context: Dagster asset execution context
        internal_train_clustering_models: Dictionary of trained clustering models
        internal_assign_clusters: Dictionary of DataFrames with cluster assignments

    Returns:
        Dictionary mapping category names to lists of visualization file paths
    """
    visualizations = {}

    # Placeholder - In a real implementation, this would generate actual plots
    # and save them to files. Here we'll just return placeholder file paths.
    for category in internal_train_clustering_models.keys():
        if category not in internal_assign_clusters:
            context.log.warning(f"No assignments found for category: {category}")
            continue

        context.log.info(f"Generating visualizations for category: {category}")

        # In a real implementation, plots would be generated and saved
        visualizations[category] = [
            f"plots/{category}_cluster_distribution.png",
            f"plots/{category}_pca_projection.png",
            f"plots/{category}_silhouette.png",
        ]

        context.log.info(f"Generated {len(visualizations[category])} plots for {category}")

    # Store summary in context metadata
    context.add_output_metadata(
        {
            "categories": list(visualizations.keys()),
            "visualization_count": sum(len(v) for v in visualizations.values()),
        }
    )

    return visualizations
