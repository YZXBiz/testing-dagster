"""Settings and configuration for the clustering dashboard using Pydantic.

This module defines the settings for the clustering dashboard using Pydantic Settings for robust
configuration management, validation, and environment variable overrides.
"""

from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class ThemeConfig(BaseSettings):
    """Dashboard theme configuration."""

    primary_color: str = "#4CAF50"  # A vibrant green for interactive elements
    background_color: str = "#1E1E1E"  # Dark background for better contrast
    secondary_background_color: str = "#252526"  # Slightly lighter than background
    text_color: str = "#FFFFFF"  # White text for readability
    font: str = "sans serif"


class DashboardSettings(BaseSettings):
    """Dashboard configuration settings."""

    # Dashboard title and description
    dashboard_title: str = "Clustering Merging Dashboard"
    dashboard_subtitle: str = "Visualize and explore merging cluster assignments"

    # Default assets to show in the dashboard - ONLY from merging module
    default_assets: list[str] = [
        "merged_cluster_assignments",
        "cluster_reassignment",
        "merged_clusters",
        "optimized_merged_clusters",
    ]

    # Dashboard layout and UI settings
    layout: str = "wide"  # "wide" or "centered"
    sidebar_state: str = "expanded"  # "expanded" or "collapsed"
    theme: ThemeConfig = ThemeConfig()

    # Feature settings
    max_features_to_display: int = 20  # Maximum number of features to display in visualizations

    # Paths - focused specifically on merging data
    storage_path: Path = Path(__file__).parent.parent.parent.parent.parent / "data" / "merging"
    data_path: Path = Path(__file__).parent.parent.parent.parent.parent / "data" / "merging"

    # Visualization settings
    chart_height: int = 500  # Default height for charts
    color_scales: dict[str, str] = {
        "sequential": "Viridis",
        "diverging": "RdBu",
        "categorical": "Set1",
    }

    # Map of asset types to their descriptions - ONLY merging assets
    asset_descriptions: dict[str, str] = {
        "cluster_reassignment": "Final cluster assignments after small cluster reassignment",
        "merged_clusters": "Combined internal and external clusters before optimization",
        "optimized_merged_clusters": "Dictionary with small and large clusters identified",
        "merged_cluster_assignments": "Mapping of merged cluster assignments with counts",
    }

    # Default visualizations to show for each asset type
    default_visualizations: dict[str, list[str]] = {
        "cluster_reassignment": ["cluster_distribution", "feature_scatter", "comparison"],
        "merged_clusters": ["cluster_distribution", "feature_scatter", "parallel_coordinates"],
        "optimized_merged_clusters": ["cluster_distribution", "feature_scatter"],
    }

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="DASHBOARD_",  # Environment variables will be prefixed with DASHBOARD_
        env_file=".env",  # Load values from .env file
        extra="ignore",  # Ignore extra fields
        case_sensitive=False,  # Case-insensitive env vars
    )


# Create a settings instance for use throughout the application
settings = DashboardSettings()
