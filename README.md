
  
# TDEI python lib formatter library  

[![codecov](https://codecov.io/gh/TaskarCenterAtUW/TDEI-python-lib-osw-formatter/branch/main/graph/badge.svg)](https://codecov.io/gh/TaskarCenterAtUW/TDEI-python-lib-osw-formatter)
  
This python package designed to convert geospatial data from one format to another. In this case, it converts data from OpenStreetMap (OSM) format to OpenSideWalks (OSW) format and OpenSideWalks (OSW) format to OpenStreetMap (OSM) format. Let's break down the key components and processes involved in this converter:    
    
## OpenStreetMap (OSM) to OpenSideWalks (OSW)  
Converting OSM data to OSW is essential for creating accurate and detailed pedestrian-related datasets that can be used to improve pedestrian accessibility and mobility in urban environments. This data can be valuable for research, infrastructure development, and improving the pedestrian experience in cities and communities.  
  
 1. **Converter Purpose:** Converting OSM data to OSW is essential for creating accurate and detailed pedestrian-related datasets that can be used to improve pedestrian accessibility and mobility in urban environments. This data can be valuable for research, infrastructure development, and improving the pedestrian experience in cities and communities.    
 2. **Input Data:** The converter typically takes OSM data as its input. OSM data can be in the form of OSM files (PBF binary or plain XML format), which contain geographic elements, their attributes, and relationships.    
 3. **Output Data:** The result of the conversion is OSW data. This output is a representation of geographic features using the OSW schema. The OSW format might have specific attributes and structures points, nodes and edges.    
  
## OpenSideWalks (OSW) to OpenStreetMap (OSM)  
The conversion of OSW data to OSM is beneficial for incorporating detailed pedestrian and accessibility data into the broader OSM database. This integrated dataset can enhance the completeness and accuracy of OSM and can be valuable for pedestrian accessibility assessments, navigation applications, and urban planning initiatives that require comprehensive geospatial data.  
  
 1. **Converter Purpose:** Converting OpenSidewalks (OSW) data to OpenStreetMap (OSM) involves the transformation of pedestrian-related geospatial data from the OSW format into the OSM format. OpenSidewalks is a platform that focuses on pedestrian infrastructure, accessibility features, and sidewalk-related data. The conversion process allows for the integration of pedestrian data into the more comprehensive OSM database, which includes various types of geospatial data.    
 2. **Input Data:** The converter typically takes OSW data as its input. OSW data can be in the form of OSW files (geojson files of nodes, edges and points), which contain specific attributes and structures points, nodes and edges.    
 3. **Output Data:** The result of the conversion is OSM data. This output is a representation of OSM XML file.    
  
  
## System requirements  
  
| Software | Version |  
|----------|---------|  
| Python   | 3.10.x  |  
| GDAL     | 3.4.1   |  
  
## Establishing python env for the project
Running the code base requires a proper Python environment set up. The following lines of code helps one establish such env named `tdei-osw`. replace `tdei-osw` with the name of your choice.

```
conda create -n tdei-osw python=3.10 gdal
conda activate tdei-osw
pip install -r requirements.txt
```
Alternatively one can use the `setup_env.sh` script provided with this repo. One can run 
`source ./setup_env.sh`. Once run, the command creates an environment with the name `tdei`

## How to install GDAL   
If for some reason the above conda creation fails to install GDAL, please follow the procedure below.
  
To install the GDAL library (Geospatial Data Abstraction Library) on your system, you can follow the steps below. The specific installation process may vary depending on your operating system.  
  
1. **Linux (Ubuntu/Debian):**  GDAL is available in the Ubuntu and Debian repositories. You can install it using apt: 
    ``` 
    sudo apt update 
    sudo apt install gdal-bin libgdal-dev python3-gdal 
    ```
   
  2.   **Linux (CentOS/RHEL):** On CentOS/RHEL, you can install GDAL using `yum`:
        ``` 
        sudo yum install gdal 
        ```  
	    
  3. **macOS (Homebrew):** If you're using Homebrew on macOS, you can install GDAL with the following command:
      ```
      brew install gdal
      ```
  4. **Windows:** On Windows, you can install GDAL using the GDAL Windows binaries provided by the GIS Internals project:
  
        1. Go to the [GIS Internals download page](https://www.gisinternals.com/release.php).
        2. Choose the GDAL version that matches your system (e.g., 32-bit or 64-bit) and download the core components.
        3. Install the downloaded MSI file.
        4. Make sure to add the GDAL bin directory to your system's PATH variable if it's not added automatically.
  
## What this package does

1. osm2osw
   1. It takes the OSM file (pbf or xml) and output directory path(optional) as input
   2. Process the osm file
   3. Convert the osm file into edges.geojson, points.geojson, nodes.geojson, zones.geojson, polygons.geojson and lines.geojson files at provided output directory path

2. osw2osm  
   1. It takes the `zip` file which contains edges.geojson, points.geojson, nodes.geojson, zones.geojson, polygons.geojson and lines.geojson files, and output directory path(optional) as input
   2. Process the geojson files
   3. Convert those files into xml file at provided output directory path   

## Custom attributes (OSW 0.3)
- Custom features that contain only `ext:*` attributes are preserved and written to their matching GeoJSON:
  - Point geometries → `points.geojson` with numeric `_id` (no `p` prefix) and `ext:osm_id`.
  - LineString geometries → `lines.geojson` with `_id`, `_u_id`, `_v_id`, plus `ext:*`.
  - Polygon geometries → `polygons.geojson` with `_id` and `ext:*`.
- Outputs are formatted with indentation to simplify inspection.

  
## Starting a new project with template  
  
- Add `osm-osw-reformatter` package as dependency in your `requirements.txt`  
- or `pip install osm-osw-reformatter`  
- Start using the packages in your code.  

```python  
import asyncio
from osm_osw_reformatter import Formatter  
  
async def osm_convert():
    f = Formatter(workdir=<OUTPUT_DIR>, file_path=<OSM_INPUT_FILE>)
    return await f.osm2osw()
    # Uncomment below line to clean up the generated files
    # f.cleanup()


def osw_convert():
    f = Formatter(workdir=<OUTPUT_DIR>, file_path=<OSW_INPUT_FILE>)
    return f.osw2osm()
    # Uncomment below line to clean up the generated files
    # f.cleanup()


if __name__ == '__main__':
    results = asyncio.run(osm_convert())
    print(results.generated_files)
    osw_convert()  
```  
  
  
### Testing  
  
The project is configured with `python` to figure out the coverage of the unit tests. All the tests are in `tests`  
folder.  
  
- To execute the tests, please follow the commands:  
  
    ```
    pip install -r requirements.txt
    python -m unittest discover -v tests/unit_tests
    ```  
    
  
- To execute the code coverage, please follow the commands:  
  
    ```
    python -m coverage run --source=src -m unittest discover -v tests/unit_tests
    coverage html                                                       // Can be run after 1st command
    coverage report                                                     // Can be run after 1st command 
    ```
  

- After the commands are run, you can check the coverage report in `htmlcov/index.html`. Open the file in any browser,  
  and it shows complete coverage details  
- The terminal will show the output of coverage like this  
  
```shell  
>  python -m coverage run --source=src -m unittest discover tests/unit_tests  
.................................
..................................

----------------------------------------------------------------------
Ran 225 tests in 44.601s

OK
```
