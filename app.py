import streamlit as st
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import plotly.express as px
import json
import os

# ----------------------------
# Function to Extract Largest Polygon
# ----------------------------
def get_largest_polygon(geometry):
    """
    Extracts the largest Polygon from a MultiPolygon geometry.
    If the geometry is already a Polygon, it is returned as is.
    Returns None for unsupported geometry types.
    """
    if isinstance(geometry, MultiPolygon):
        # Ensure there is at least one polygon in the MultiPolygon
        if len(geometry.geoms) == 0:
            return None
        return max(geometry.geoms, key=lambda p: p.area)
    elif isinstance(geometry, Polygon):
        return geometry
    else:
        return None

# ----------------------------
# Load and Process Data
# ----------------------------
@st.cache_data
def load_data(shapefile_path):
    """
    Loads and processes the shapefile.

    Parameters:
    - shapefile_path (str): Path to the .shp file.

    Returns:
    - GeoDataFrame: Processed GeoDataFrame with land_ratio calculated.
    """
    if not os.path.exists(shapefile_path):
        st.error(f"Shapefile not found at `{shapefile_path}`. Please ensure the file exists.")
        st.stop()

    # Load the shapefile into a GeoDataFrame
    try:
        geo_df = gpd.read_file(shapefile_path)
    except Exception as e:
        st.error(f"Error loading shapefile: {e}")
        st.stop()

    geo_df['filter1'] = geo_df['STATEFP'].astype(int)
    geo_df = geo_df[geo_df['filter1']<57]

    # Make a copy for processing
    gdf = geo_df.copy()

    # Identify Alaska rows using the FIPS code '02'
    alaska_fips = '02'
    is_alaska = gdf['STATEFP'] == alaska_fips
    st.write(f"**Number of Alaska records before modification:** {is_alaska.sum()}")

    # Extract the largest polygon for Alaska geometries
    gdf.loc[is_alaska, 'geometry'] = gdf.loc[is_alaska, 'geometry'].apply(get_largest_polygon)

    # Remove any Alaska rows where geometry is None (if any)
    gdf = gdf[~(is_alaska & gdf['geometry'].isnull())].copy()

    # Reset index for cleanliness
    gdf.reset_index(drop=True, inplace=True)
    st.write(f"**Number of Alaska records after modification:** {(gdf['STATEFP'] == alaska_fips).sum()}")

    # Reproject to WGS84 (EPSG:4326)
    gdf = gdf.to_crs(epsg=4326)
    st.write(f"**GeoDataFrame CRS after projection:** {gdf.crs}")

    # Calculate the land ratio: ALAND / (ALAND + AWATER)
    gdf['land_ratio'] = gdf['ALAND'] / (gdf['ALAND'] + gdf['AWATER'])

    # Handle potential division by zero (if ALAND + AWATER is zero)
    gdf['land_ratio'] = gdf['land_ratio'].fillna(0)

    return gdf

# ----------------------------
# Create Choropleth Map
# ----------------------------
def create_choropleth_map(gdf):
    # Convert GeoDataFrame to GeoJSON
    geojson = json.loads(gdf.to_json())

    # Define a custom color scale that emphasizes blue
    custom_color_scale = [
        (0.0, 'blue'),
        (0.7, 'blue'),   # Blue up to 70% of the color scale
        (1.0, 'green')   # Green from 70% to 100%
    ]

    # Create the choropleth map using Plotly Express
    fig = px.choropleth(
        gdf,
        geojson=geojson,
        locations='GEOID',                # Column in gdf that matches 'id' in geojson
        color='land_ratio',               # Column to set color
        color_continuous_scale=custom_color_scale,
        range_color=(0, 1),
        scope="usa",                      # Focus the map on the USA
        labels={'land_ratio': 'Land Ratio'},
        hover_data={'GEOID': True, 'land_ratio': ':.2f'},  # Customize hover information
        featureidkey="properties.GEOID"   # Ensure correct mapping between GeoJSON and DataFrame
    )

    # Update layout for better visualization
    fig.update_layout(
        title_text='US Congressional Districts by Land/Water Ratio',
        title_x=0.5,
        geo=dict(
            showframe=False,
            showcoastlines=False,
            projection_type='albers usa'    # Albers projection for USA
        ),
        coloraxis_colorbar=dict(
            title="Land Ratio<br>(Green=More Land, Blue=More Water)"
        )
    )

    return fig
def create_histogram(gdf):
    # Example: Histogram of Land Ratios
    fig_hist = px.histogram(
        gdf,
        x='land_ratio',
        nbins=50,
        title="Histogram of Land Ratios",
        labels={'land_ratio': 'Land Ratio', 'count': 'Number of Districts'},
        color_discrete_sequence=['green']
    )
    fig_hist.update_layout(
        xaxis_title="Land Ratio",
        yaxis_title="Number of Districts"
    )
    return fig_hist

def create_scatter_plot(gdf):
    # Example: Scatter Plot of ALAND vs. AWATER
    fig_scatter = px.scatter(
        gdf,
        x='ALAND',
        y='AWATER',
        size='land_ratio',
        color='land_ratio',
        hover_data=['GEOID'],
        title="Scatter Plot of Land Area vs. Water Area",
        labels={'ALAND': 'Land Area (Square Meters)', 'AWATER': 'Water Area (Square Meters)'},
        color_continuous_scale='Blues'
    )
    fig_scatter.update_layout(
        xaxis_title="Land Area (Square Meters)",
        yaxis_title="Water Area (Square Meters)"
    )
    return fig_scatter

# ----------------------------
# Main Streamlit App
# ----------------------------
def main():
    st.set_page_config(page_title="US Congressional Districts Visualization", layout="wide")

    st.title("US Congressional Districts Visualization")

    # Define the path to the shapefile
    shapefile_dir = './shapefile/'
    shapefile_name = 'house_districts_2024.shp'
    shapefile_path = os.path.join(shapefile_dir, shapefile_name)

    # Check if the shapefile directory exists
    if not os.path.exists(shapefile_dir):
        st.error(f"The directory `{shapefile_dir}` does not exist. Please create it and add the shapefile.")
        st.stop()

    # Check if the shapefile exists
    if not os.path.exists(shapefile_path):
        st.error(f"The shapefile `{shapefile_name}` does not exist in `{shapefile_dir}`. Please add it along with its components.")
        st.stop()

    # Load and process the data
    with st.spinner("Loading and processing data..."):
        gdf = load_data(shapefile_path)

    # Create tabs
    tabs = st.tabs(["Choropleth Map", "Histogram", "Scatter Plot"])

    # ----------------------------
    # Tab 1: Choropleth Map
    # ----------------------------
    with tabs[0]:
        st.header("Land-to-Water Ratio Choropleth Map")
        st.markdown("""
        This map visualizes the land-to-water ratio of US congressional districts. 
        **Green** indicates a higher proportion of land, while **blue** signifies a greater presence of water bodies.
        """)

        fig = create_choropleth_map(gdf)

        st.plotly_chart(fig, use_container_width=True)

    # ----------------------------
    # Tab 2: Histogram
    # ----------------------------
    with tabs[1]:
        st.header("Distribution of Land Ratios")
        st.markdown("""
        The histogram below shows the distribution of land-to-water ratios across all congressional districts.
        """)

        fig_hist = create_histogram(gdf)

        st.plotly_chart(fig_hist, use_container_width=True)

    # ----------------------------
    # Tab 3: Scatter Plot
    # ----------------------------
    with tabs[2]:
        st.header("Land Area vs. Water Area")
        st.markdown("""
        The scatter plot illustrates the relationship between land area and water area for each congressional district. 
        The size and color of each point represent the land-to-water ratio.
        """)

        fig_scatter = create_scatter_plot(gdf)

        st.plotly_chart(fig_scatter, use_container_width=True)

    # ----------------------------
    # Footer
    # ----------------------------
    st.markdown("---")
    st.markdown("© 2024 Your Name. All rights reserved.")

if __name__ == "__main__":
    main()