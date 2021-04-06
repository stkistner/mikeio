from datetime import datetime, timedelta
from abc import abstractmethod

import warnings
import numpy as np
import pandas as pd
from tqdm import tqdm, trange
from .dataset import Dataset
from .base import TimeSeries

from .dotnet import (
    to_dotnet_datetime,
    from_dotnet_datetime,
    to_numpy,
    to_dotnet_float_array,
)
from .eum import ItemInfo, TimeStepUnit, EUMType, EUMUnit
from .custom_exceptions import DataDimensionMismatch, ItemNumbersError
from .dfsutil import _valid_item_numbers, _valid_timesteps, _get_item_info
from DHI.Generic.MikeZero import eumQuantity
from DHI.Generic.MikeZero.DFS import (
    DfsSimpleType,
    DataValueType,
    DfsFactory,
)


class _Dfs123(TimeSeries):

    _filename = None
    _projstr = None
    _start_time = None
    _end_time = None
    _is_equidistant = True
    _items = None
    _builder = None
    _factory = None
    _deletevalue = None
    _override_coordinates = False
    _timeseries_unit = TimeStepUnit.SECOND
    _dt = None

    show_progress = False

    def __init__(self, filename=None):
        self._filename = filename

    def read(self, items=None, time_steps=None):
        """
        Read data from a dfs file

        Parameters
        ---------
        items: list[int] or list[str], optional
            Read only selected items, by number (0-based), or by name
        time_steps: str, int or list[int], optional
            Read only selected time_steps

        Returns
        -------
        Dataset
        """
        self._open()

        item_numbers = _valid_item_numbers(self._dfs.ItemInfo, items)
        n_items = len(item_numbers)

        time_steps = _valid_timesteps(self._dfs.FileInfo, time_steps)
        nt = len(time_steps)

        if self._ndim == 1:
            shape = (nt, self._nx)
        elif self._ndim == 2:
            shape = (nt, self._ny, self._nx)
        else:
            shape = (nt, self._nz, self._ny, self._nx)

        data_list = [np.ndarray(shape=shape) for item in range(n_items)]

        t_seconds = np.zeros(len(time_steps))

        for i, it in enumerate(tqdm(time_steps, disable=not self.show_progress)):
            for item in range(n_items):

                itemdata = self._dfs.ReadItemTimeStep(item_numbers[item] + 1, it)

                src = itemdata.Data
                d = to_numpy(src)

                d[d == self.deletevalue] = np.nan

                if self._ndim == 2:
                    d = d.reshape(self._ny, self._nx)
                    d = np.flipud(d)

                data_list[item][i] = d

            t_seconds[i] = itemdata.Time

        time = [self.start_time + timedelta(seconds=t) for t in t_seconds]

        items = _get_item_info(self._dfs.ItemInfo, item_numbers)

        self._dfs.Close()
        return Dataset(data_list, time, items)

    def _read_header(self):
        dfs = self._dfs
        self._n_items = len(dfs.ItemInfo)
        self._items = _get_item_info(dfs.ItemInfo, list(range(self._n_items)))
        self._start_time = from_dotnet_datetime(dfs.FileInfo.TimeAxis.StartDateTime)
        if hasattr(dfs.FileInfo.TimeAxis, "TimeStep"):
            self._timestep_in_seconds = (
                dfs.FileInfo.TimeAxis.TimeStep
            )  # TODO handle other timeunits
            # TODO to get the EndTime
        self._n_timesteps = dfs.FileInfo.TimeAxis.NumberOfTimeSteps
        self._projstr = dfs.FileInfo.Projection.WKTString
        self._longitude = dfs.FileInfo.Projection.Longitude
        self._latitude = dfs.FileInfo.Projection.Latitude
        self._orientation = dfs.FileInfo.Projection.Orientation
        self._deletevalue = dfs.FileInfo.DeleteValueFloat

        dfs.Close()

    def _write(
        self, filename, data, start_time, dt, datetimes, items, coordinate, title
    ):

        if isinstance(data, Dataset) and not data.is_equidistant:
            datetimes = data.time

        self._write_handle_common_arguments(
            title, data, items, coordinate, start_time, dt
        )

        shape = np.shape(data[0])
        if self._ndim == 1:
            self._nx = shape[1]
        elif self._ndim == 2:
            self._ny = shape[1]
            self._nx = shape[2]

        self._factory = DfsFactory()
        self._set_spatial_axis()

        if self._ndim == 1:
            if not all(np.shape(d)[1] == self._nx for d in data):
                raise DataDimensionMismatch()

        if self._ndim == 2:
            if not all(np.shape(d)[1] == self._ny for d in data):
                raise DataDimensionMismatch()

            if not all(np.shape(d)[2] == self._nx for d in data):
                raise DataDimensionMismatch()
        if datetimes is not None:
            self._is_equidistant = False
            start_time = datetimes[0]
            self._start_time = start_time

        dfs = self._setup_header(filename)

        deletevalue = dfs.FileInfo.DeleteValueFloat  # -1.0000000031710769e-30

        for i in trange(self._n_timesteps, disable=not self.show_progress):
            for item in range(self._n_items):

                d = self._data[item][i]
                d = d.copy()  # to avoid modifying the input
                d[np.isnan(d)] = deletevalue

                if self._ndim == 1:
                    darray = to_dotnet_float_array(d)

                if self._ndim == 2:
                    d = d.reshape(self.shape[1:])
                    d = np.flipud(d)
                    darray = to_dotnet_float_array(d.reshape(d.size, 1)[:, 0])
                if self._is_equidistant:
                    dfs.WriteItemTimeStepNext(0, darray)
                else:
                    t = datetimes[i]
                    relt = (t - start_time).total_seconds()
                    dfs.WriteItemTimeStepNext(relt, darray)

        dfs.Close()

    def _write_handle_common_arguments(
        self, title, data, items, coordinate, start_time, dt
    ):

        if title is None:
            self._title = ""

        self._n_timesteps = np.shape(data[0])[0]
        self._n_items = len(data)

        if coordinate is None:
            if self._projstr is not None:
                self._coordinate = [
                    self._projstr,
                    self._longitude,
                    self._latitude,
                    self._orientation,
                ]
            else:
                warnings.warn("No coordinate system provided")
                self._coordinate = ["LONG/LAT", 0, 0, 0]
        else:
            self._override_coordinates = True
            self._coordinate = coordinate

        if isinstance(data, Dataset):
            self._items = data.items
            self._start_time = data.time[0]
            if dt is None and len(data.time) > 1:
                self._dt = (data.time[1] - data.time[0]).total_seconds()
            self._data = data.data
        else:
            self._data = data

        if start_time is None:
            if self._start_time is None:
                self._start_time = datetime.now()
                warnings.warn(
                    f"No start time supplied. Using current time: {self._start_time} as start time."
                )
            else:
                self._start_time = self._start_time
        else:
            self._start_time = start_time

        if dt:
            self._dt = dt

        if self._dt is None:
            self._dt = 1
            warnings.warn("No timestep supplied. Using 1s.")

        if items:
            self._items = items

        if self._items is None:
            self._items = [ItemInfo(f"Item {i+1}") for i in range(self._n_items)]

        self._timeseries_unit = TimeStepUnit.SECOND

    def _setup_header(self, filename):

        system_start_time = to_dotnet_datetime(self._start_time)

        self._builder.SetDataType(0)

        if self._coordinate[0] == "LONG/LAT":
            proj = self._factory.CreateProjectionGeoOrigin(*self._coordinate)
        else:
            if self._override_coordinates:
                proj = self._factory.CreateProjectionProjOrigin(*self._coordinate)
            else:
                proj = self._factory.CreateProjectionGeoOrigin(*self._coordinate)

        self._builder.SetGeographicalProjection(proj)

        if self._is_equidistant:
            self._builder.SetTemporalAxis(
                self._factory.CreateTemporalEqCalendarAxis(
                    self._timeseries_unit, system_start_time, 0, self._dt
                )
            )
        else:
            self._builder.SetTemporalAxis(
                self._factory.CreateTemporalNonEqCalendarAxis(
                    self._timeseries_unit, system_start_time
                )
            )

        for item in self._items:
            self._builder.AddDynamicItem(
                item.name,
                eumQuantity.Create(item.type, item.unit),
                DfsSimpleType.Float,
                item.data_value_type,
            )

        try:
            self._builder.CreateFile(filename)
        except IOError:
            # TODO does this make sense?
            print("cannot create dfs file: ", filename)

        return self._builder.GetFile()

    def _open(self):
        raise NotImplementedError("Should be implemented by subclass")

    def _set_spatial_axis(self):
        raise NotImplementedError("Should be implemented by subclass")

    @property
    def deletevalue(self):
        "File delete value"
        return self._deletevalue

    @property
    def n_items(self):
        "Number of items"
        return self._n_items

    @property
    def items(self):
        "List of items"
        return self._items

    @property
    def start_time(self):
        """File start time"""
        return self._start_time

    @property
    def end_time(self):
        """File end time"""
        if self._end_time is None:
            self._end_time = self.read([0]).time[-1].to_pydatetime()

        return self._end_time

    @property
    def n_timesteps(self):
        """Number of time steps"""
        return self._n_timesteps

    @property
    def timestep(self):
        """Time step size in seconds"""
        return self._timestep_in_seconds

    @property
    def projection_string(self):
        return self._projstr

    @property
    def longitude(self):
        """Origin longitude"""
        return self._longitude

    @property
    def latitude(self):
        """Origin latitude"""
        return self._latitude

    @property
    def orientation(self):
        """North to Y orientation"""
        return self._orientation

    @property
    @abstractmethod
    def dx(self):
        """Step size in x direction"""
        pass