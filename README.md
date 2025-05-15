# CGMES2PGM-Suite

`cgmes2pgm_suite` provides additional tools for `cgmes2pgm_converter` to integrate [PowerGridModel](https://github.com/PowerGridModel/power-grid-model) with the Common Grid Model Exchange Standard (CGMES).
It focuses on performing the state estimation on CGMES datasets.

## Features

- Human readable exports of PGM Datasets in TXT and Excel
- Debug state estimation by manipulating datasets (e.g., subnet splitting)
- Configure conversion and state estimation via a configuration file
- Simulate measurements:
  - when real measurements are not provided via an Operation Profile, but a State Variable (SV) Profile is available
  - generates an Operation Profile with distorted measurements based on the SV Profile

## Installation

### Install from PyPI

The package can be installed via pip:

```bash
pip install cgmes2pgm_suite
```

## Usage

[Example](./example) contains examples on how to use the package.

### Running as Standalone

This package can be run as a standalone application, performing the conversion and running PGM's state estimation. To do so, you need to install the package and then run the following command:

```bash
python -m cgmes2pgm_suite --config <path_to_config_file>
```

The provided configuration file contains the dataset configuration and the parameters for the conversion and state estimation.
An example configuration file can be found in [/example](./example).

### Datasets

The conversion, measurement simulation and state estimation has been tested with the CGMES conformity datasets.
These datasets can be obtained from [ENTSO-E CIM Conformity and Interoperability](https://www.entsoe.eu/data/cim/cim-conformity-and-interoperability/)
respecting their License.

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

The configuration used for the `SmallGrid` dataset is located at [./example/SmallGrid.yaml](./example/SmallGrid.yaml) and can be executed with the following command:

```bash
python -m cgmes2pgm_suite --config ./example/SmallGrid.yaml
```

See [state_estimation.ipynb](./example/state_estimation.ipynb) on how to create the required SPARQL endpoint.

Dataset Version: CGMES Conformity Assessment Scheme Test Configurations v3.0.2

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
