import streamlit as st
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import plotly.express as px
import json
import os
st.markdown("""
    <style>
    .reportview-container {
        background: white;
    }
    .main {
        background-color: white;
    }
    </style>
    """, unsafe_allow_html=True)
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


    # Identify Alaska rows using the FIPS code '02'
    alaska_fips = '02'
    is_alaska = geo_df['STATEFP'] == alaska_fips

    # Extract the largest polygon for Alaska geometries
    geo_df.loc[is_alaska, 'geometry'] = geo_df.loc[is_alaska, 'geometry'].apply(get_largest_polygon)

    # Remove any Alaska rows where geometry is None (if any)
    geo_df = geo_df[~(is_alaska & geo_df['geometry'].isnull())].copy()

    # Reset index for cleanliness
    geo_df.reset_index(drop=True, inplace=True)

    # Reproject to WGS84 (EPSG:4326)
    #geo_df = geo_df.to_crs(epsg=4326)
    st.write(f"**GeoDataFrame CRS after projection:** {geo_df.crs}")

    # Calculate the land ratio: ALAND / (ALAND + AWATER)
    geo_df['land_ratio'] = geo_df['ALAND'] / (geo_df['ALAND'] + geo_df['AWATER'])

    # Handle potential division by zero (if ALAND + AWATER is zero)
    geo_df['land_ratio'] = geo_df['land_ratio'].fillna(0)

    return geo_df

# ----------------------------
# Create Choropleth Map
# ----------------------------
def create_choropleth_map(geo_df):
    # Convert GeoDataFrame to GeoJSON
    geojson = json.loads(geo_df.to_json())

    # Define a custom color scale that emphasizes blue
    custom_color_scale = [
        (0.0, 'blue'),
        (0.7, 'blue'),   # Blue up to 70% of the color scale
        (1.0, 'green')   # Green from 70% to 100%
    ]

    # Create the choropleth map using Plotly Express
    fig = px.choropleth(
        geo_df,
        geojson=geojson,
        locations='GEOID',                # Column in geo_df that matches 'id' in geojson
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

    )

    return fig


# ----------------------------
# Main Streamlit App
# ----------------------------
def main():

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
        geo_df = load_data(shapefile_path)

   

    # Create the choropleth map
    fig = create_choropleth_map(geo_df)

    # Display the map
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
