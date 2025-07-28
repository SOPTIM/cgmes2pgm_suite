# CGMES2PGM-Suite

`cgmes2pgm_suite` provides additional tools for `cgmes2pgm_converter` to integrate [PowerGridModel](https://github.com/PowerGridModel/power-grid-model) with the Common Grid Model Exchange Standard (CGMES).
It focuses on performing the state estimation on CGMES datasets.

## Features

- Start an Apache Jena Fuseki as docker container
- Upload Datasets to a SPARQL endpoint
- Human readable exports of PGM Datasets in TXT and Excel
- Create SV-Profile from PGM Results
- Debug state estimation by manipulating datasets (e.g., subnet splitting)
- Configure conversion and state estimation via a configuration file
- Simulate measurements:
  - when real measurements are not provided via an Operation Profile, but a State Variable (SV) Profile is available
  - generates an Operation Profile with distorted measurements based on the SV Profile

## Installation

The package can be installed via pip:

```bash
pip install cgmes2pgm_suite
```

To start an Apache Jena Fuseki server via this package, Docker is required.
See [Docker installation guide](https://docs.docker.com/engine/install/).

## Usage

This package can be run as a standalone application, performing the conversion and running PGM's state estimation. To do so, you need to install the package and then run the following command:

```bash
python -m cgmes2pgm_suite --config <path_to_config_file>
```

The provided configuration file contains the dataset configuration and the parameters for the conversion and state estimation.
An example configuration file can be found in [/example](./example).

### Quick Start

For a quick start, we recommend cloning this project and using the provided test cases.

If the project is cloned, setup the environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
pre-commit install
```

To run the Conformity Datasets, you need to download `Test Configurations v3.0.3` from [ENTSO-E CIM Conformity and Interoperability](https://www.entsoe.eu/data/cim/cim-conformity-and-interoperability/) respecting their License.
Place the rdf/xml files of each dataset in the respective subdirectory of `tests/datasets`.

Afterwards, you can run all datasets using:

```bash
pytest -m "integration"
```

> Note: Running the tests creates a Fuseki Docker container on port 3030.
> The container is automatically removed after the tests are finished.

The results of the tests can be found in the `tests/out` directory.

If you want to add your own datasets, the following steps are required:

- Place the rdf/xml files in the `tests/data/` directory
- Create a configuration file in the `tests/configs/` directory, by copying an existing one
- Update the name, output directory and location of the rdf/xml files in the new configuration file

### Datasets

The conversion, measurement simulation and state estimation has been tested with the CGMES conformity datasets.

The following datasets have been tested:

| Dataset | Size (Nodes) | Estimation Result | Comment |
| --- | --- | --- | --- |
| PowerFlow | 2 | 🟢 | |
| PST | 2 | 🟢 | All three Scenarios |
| MiniGrid | 13 | 🟢 | |
| MicroGrid | 13 | 🟢 | PST with AsymmetricalPhaseTapChanger (BE-TR2_2) has been split |
| SmallGrid | 167 | 🟢 | |
| Svedala | 191 | 🟢 | |
| RealGrid | 6051 | 🟡 | Requires smaller sigmas in measurement simulation to converge |
| FullGrid | 26 | ? | SV-Profile does not contain power flows for all branches, resulting in an insufficient amount of simulated measurements |

> Dataset Version: CGMES Conformity Assessment Scheme Test Configurations v3.0.2

The used configuration files can be found in the [/tests/configs](./tests/configs) directory.

## License

This project is licensed under the [Apache License 2.0](LICENSE.txt).

## Dependencies

This project includes third-party dependencies, which are licensed under their own respective licenses.

- [cgmes2pgm_converter](https://pypi.org/project/cgmes2pgm_converter/) (Apache License 2.0)
- [bidict](https://pypi.org/project/bidict/) (Mozilla Public License 2.0)
- [numpy](https://pypi.org/project/numpy/) (BSD License)
- [pandas](https://pypi.org/project/pandas/) (BSD License)
- [power-grid-model](https://pypi.org/project/power-grid-model/) (Mozilla Public License 2.0)
- [power-grid-model-io](https://pypi.org/project/power-grid-model-io/) (Mozilla Public License 2.0)
- [SPARQLWrapper](https://pypi.org/project/SPARQLWrapper/) (W3C License)
- [XlsxWriter](https://pypi.org/project/XlsxWriter/) (BSD License)
- [PyYAML](https://pypi.org/project/PyYAML/) (MIT License)
- [StrEnum](https://pypi.org/project/StrEnum/) (MIT License)
- [docker](https://pypi.org/project/docker/) (Apache License 2.0)

This project includes code from [jena-fuseki-docker](https://repo1.maven.org/maven2/org/apache/jena/jena-fuseki-docker/)
in the `src/cgmes2pgm_suite/resources/docker` directory, which is redistributed under the original Apache License 2.0.
See the root‑level [`NOTICE`](./NOTICE) file for full attribution.

## Commercial Support and Services

For organizations requiring commercial support, professional maintenance, integration services,
or custom extensions for this project, these services are available from **SOPTIM AG**.

Please feel free to contact us via [powergridmodel@soptim.de](mailto:powergridmodel@soptim.de).

## Contributing

We welcome contributions to improve this project.
Please see our [Contributing Guide](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and suggest improvements.

## Code of Conduct

This project adheres to a code of conduct adapted from the [Apache Foundation's Code of Conduct](https://www.apache.org/foundation/policies/conduct).
We expect all contributors and users to follow these guidelines to ensure a welcoming and inclusive community.
