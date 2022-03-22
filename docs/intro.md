
**The documentation is currently being updated to reflect the upcoming version of MIKE IO 1.0**

Requirements
------------

* Windows or Linux operating system
* Python x64 3.7 - 3.10
* (Windows) `VC++ redistributables <https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads>`_ (already installed if you have MIKE)

Installation
------------

    pip install mikeio

Getting started
---------------
    
    >>>  import
    >>>  ds = mikeio.read('simple.dfs0')
    >>>  df = ds.to_dataframe()

Read more in the `getting started guide <getting_started.html>`_.

Notebooks
---------

`List of all notebooks <https://nbviewer.jupyter.org/github/DHI/mikeio/tree/main/notebooks/>`_

* `Dfs0 <https://nbviewer.jupyter.org/github/DHI/mikeio/blob/main/notebooks/Dfs0%20-%20Timeseries.ipynb>`_
* `Dfsu basic <https://nbviewer.jupyter.org/github/DHI/mikeio/blob/main/notebooks/Dfsu%20-%20Read.ipynb>`_
* `Create Dfs2 from netCDF <https://nbviewer.jupyter.org/github/DHI/mikeio/blob/main/notebooks/Dfs2%20-%20Bathymetry.ipynb>`_



Where can I get help?
---------------------

* New ideas and feature requests - `GitHub Discussions <http://github.com/DHI/mikeio/discussions>`_ 
* Bugs - `GitHub Issues <http://github.com/DHI/mikeio/issues>`_