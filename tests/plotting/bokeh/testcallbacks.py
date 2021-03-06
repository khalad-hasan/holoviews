from collections import deque
from unittest import SkipTest

import numpy as np

from holoviews.core import DynamicMap
from holoviews.core.options import Store
from holoviews.element import Points, Polygons, Box, Curve, Table
from holoviews.element.comparison import ComparisonTestCase
from holoviews.streams import (PointDraw, PolyDraw, PolyEdit, BoxEdit,
                               PointerXY, PointerX, PlotReset)
import pyviz_comms as comms

try:
    from bokeh.models import PolyEditTool
    from holoviews.plotting.bokeh.callbacks import (
        Callback, PointDrawCallback, PolyDrawCallback, PolyEditCallback,
        BoxEditCallback
    )
    from holoviews.plotting.bokeh.renderer import BokehRenderer
    from holoviews.plotting.bokeh.util import bokeh_version
    bokeh_server_renderer = BokehRenderer.instance(mode='server')
    bokeh_renderer = BokehRenderer.instance()
except:
    bokeh_renderer = None
    bokeh_server_renderer = None


class TestCallbacks(ComparisonTestCase):

    def setUp(self):
        self.previous_backend = Store.current_backend
        Store.current_backend = 'bokeh'

    def tearDown(self):
        Store.current_backend = self.previous_backend
        bokeh_server_renderer.last_plot = None
        bokeh_renderer.last_plot = None
        Callback._callbacks = {}

    def test_stream_callback(self):
        dmap = DynamicMap(lambda x, y: Points([(x, y)]), kdims=[], streams=[PointerXY()])
        plot = bokeh_server_renderer.get_plot(dmap)
        bokeh_server_renderer(plot)
        plot.callbacks[0].on_msg({"x": 10, "y": -10})
        data = plot.handles['source'].data
        self.assertEqual(data['x'], np.array([10]))
        self.assertEqual(data['y'], np.array([-10]))

    def test_stream_callback_with_ids(self):
        dmap = DynamicMap(lambda x, y: Points([(x, y)]), kdims=[], streams=[PointerXY()])
        plot = bokeh_server_renderer.get_plot(dmap)
        bokeh_server_renderer(plot)
        model = plot.state
        plot.callbacks[0].on_msg({"x": {'id': model.ref['id'], 'value': 10},
                                  "y": {'id': model.ref['id'], 'value': -10}})
        data = plot.handles['source'].data
        self.assertEqual(data['x'], np.array([10]))
        self.assertEqual(data['y'], np.array([-10]))

    def test_stream_callback_single_call(self):
        def history_callback(x, history=deque(maxlen=10)):
            history.append(x)
            return Curve(list(history))
        stream = PointerX(x=0)
        dmap = DynamicMap(history_callback, kdims=[], streams=[stream])
        plot = bokeh_server_renderer.get_plot(dmap)
        bokeh_server_renderer(plot)
        for i in range(20):
            stream.event(x=i)
        data = plot.handles['source'].data
        self.assertEqual(data['x'], np.arange(10))
        self.assertEqual(data['y'], np.arange(10, 20))

    def test_callback_cleanup(self):
        stream = PointerX(x=0)
        dmap = DynamicMap(lambda x: Curve([x]), streams=[stream])
        plot = bokeh_server_renderer.get_plot(dmap)
        self.assertTrue(bool(stream._subscribers))
        self.assertTrue(bool(Callback._callbacks))
        plot.cleanup()
        self.assertFalse(bool(stream._subscribers))
        self.assertFalse(bool(Callback._callbacks))


class TestResetCallback(ComparisonTestCase):

    def setUp(self):
        self.previous_backend = Store.current_backend
        Store.current_backend = 'bokeh'
        self.comm_manager = bokeh_renderer.comm_manager
        bokeh_renderer.comm_manager = comms.CommManager

    def test_reset_callback(self):
        resets = []
        def record(resetting):
            resets.append(resetting)
        curve = Curve([])
        PlotReset(source=curve).add_subscriber(record)
        plot = bokeh_server_renderer.get_plot(curve)
        plot.callbacks[0].on_msg({'reset': True})
        self.assertEqual(resets, [True])

        
class TestEditToolCallbacks(ComparisonTestCase):

    def setUp(self):
        self.previous_backend = Store.current_backend
        if not bokeh_server_renderer or bokeh_version < '0.12.14':
            raise SkipTest("Bokeh >= 0.12.14 required to test edit tool streams")
        Store.current_backend = 'bokeh'
        self.comm_manager = bokeh_renderer.comm_manager
        bokeh_renderer.comm_manager = comms.CommManager

    def tearDown(self):
        Store.current_backend = self.previous_backend
        bokeh_server_renderer.last_plot = None
        bokeh_renderer.last_plot = None
        Callback._callbacks = {}
        bokeh_renderer.comm_manager = self.comm_manager

    def test_point_draw_callback(self):
        points = Points([(0, 1)])
        point_draw = PointDraw(source=points)
        plot = bokeh_server_renderer.get_plot(points)
        self.assertIsInstance(plot.callbacks[0], PointDrawCallback)
        callback = plot.callbacks[0]
        data = {'x': [1, 2, 3], 'y': [1, 2, 3]}
        callback.on_msg({'data': data})
        self.assertEqual(point_draw.element, Points(data))

    def test_point_draw_callback_initialized_server(self):
        points = Points([(0, 1)])
        PointDraw(source=points)
        plot = bokeh_server_renderer.get_plot(points)
        self.assertEqual(plot.handles['source']._callbacks,
                         {'data': [plot.callbacks[0].on_change]})

    def test_point_draw_callback_initialized_js(self):
        points = Points([(0, 1)])
        PointDraw(source=points)
        plot = bokeh_renderer.get_plot(points)
        self.assertEqual(plot.handles['source'].js_property_callbacks,
                         {'change:data': [plot.callbacks[0].callbacks[0]]})

    def test_point_draw_callback_with_vdims_initialization(self):
        points = Points([(0, 1, 'A')], vdims=['A'])
        stream = PointDraw(source=points)
        bokeh_server_renderer.get_plot(points)
        self.assertEqual(stream.element.dimension_values('A'), np.array(['A']))
        
    def test_point_draw_callback_with_vdims(self):
        points = Points([(0, 1, 'A')], vdims=['A'])
        point_draw = PointDraw(source=points)
        plot = bokeh_server_renderer.get_plot(points)
        self.assertIsInstance(plot.callbacks[0], PointDrawCallback)
        callback = plot.callbacks[0]
        data = {'x': [1, 2, 3], 'y': [1, 2, 3], 'A': [None, None, 1]}
        callback.on_msg({'data': data})
        self.assertEqual(point_draw.element, Points(data, vdims=['A']))

    def test_poly_draw_callback(self):
        polys = Polygons([[(0, 0), (2, 2), (4, 0)]])
        poly_draw = PolyDraw(source=polys)
        plot = bokeh_server_renderer.get_plot(polys)
        self.assertIsInstance(plot.callbacks[0], PolyDrawCallback)
        callback = plot.callbacks[0]
        data = {'x': [[1, 2, 3], [3, 4, 5]], 'y': [[1, 2, 3], [3, 4, 5]]}
        callback.on_msg({'data': data})
        element = Polygons([[(1, 1), (2, 2), (3, 3)], [(3, 3), (4, 4), (5, 5)]])
        self.assertEqual(poly_draw.element, element)

    def test_poly_draw_callback_initialized_server(self):
        polys = Polygons([[(0, 0), (2, 2), (4, 0)]])
        PolyDraw(source=polys)
        plot = bokeh_server_renderer.get_plot(polys)
        self.assertEqual(plot.handles['source']._callbacks,
                         {'data': [plot.callbacks[0].on_change]})

    def test_poly_draw_callback_initialized_js(self):
        polys = Polygons([[(0, 0), (2, 2), (4, 0)]])
        PolyDraw(source=polys)
        plot = bokeh_renderer.get_plot(polys)
        self.assertEqual(plot.handles['source'].js_property_callbacks,
                         {'change:data': [plot.callbacks[0].callbacks[0]]})

    def test_poly_draw_callback_with_vdims(self):
        polys = Polygons([{'x': [0, 2, 4], 'y': [0, 2, 0], 'A': 1}], vdims=['A'])
        poly_draw = PolyDraw(source=polys)
        plot = bokeh_server_renderer.get_plot(polys)
        self.assertIsInstance(plot.callbacks[0], PolyDrawCallback)
        callback = plot.callbacks[0]
        data = {'x': [[1, 2, 3], [3, 4, 5]], 'y': [[1, 2, 3], [3, 4, 5]], 'A': [1, 2]}
        callback.on_msg({'data': data})
        element = Polygons([{'x': [1, 2, 3], 'y': [1, 2, 3], 'A': 1},
                            {'x': [3, 4, 5], 'y': [3, 4, 5], 'A': 2}], vdims=['A'])
        self.assertEqual(poly_draw.element, element)

    def test_poly_draw_callback_with_vdims_no_color_index(self):
        polys = Polygons([{'x': [0, 2, 4], 'y': [0, 2, 0], 'A': 1}], vdims=['A']).options(color_index=None)
        poly_draw = PolyDraw(source=polys)
        plot = bokeh_server_renderer.get_plot(polys)
        self.assertIsInstance(plot.callbacks[0], PolyDrawCallback)
        callback = plot.callbacks[0]
        data = {'x': [[1, 2, 3], [3, 4, 5]], 'y': [[1, 2, 3], [3, 4, 5]], 'A': [1, 2]}
        callback.on_msg({'data': data})
        element = Polygons([{'x': [1, 2, 3], 'y': [1, 2, 3], 'A': 1},
                            {'x': [3, 4, 5], 'y': [3, 4, 5], 'A': 2}], vdims=['A'])
        self.assertEqual(poly_draw.element, element)

    def test_box_edit_callback(self):
        boxes = Polygons([Box(0, 0, 1)])
        box_edit = BoxEdit(source=boxes)
        plot = bokeh_server_renderer.get_plot(boxes)
        self.assertIsInstance(plot.callbacks[0], BoxEditCallback)
        callback = plot.callbacks[0]
        source = plot.handles['rect_source']
        self.assertEqual(source.data, {'x': [0], 'y': [0], 'width': [1], 'height': [1]})
        data = {'x': [0, 1], 'y': [0, 1], 'width': [0.5, 2], 'height': [2, 0.5]}
        callback.on_msg({'data': data})
        element = Polygons([Box(0, 0, (0.5, 2)), Box(1, 1, (2, 0.5))])
        self.assertEqual(box_edit.element, element)

    def test_box_edit_callback_initialized_server(self):
        boxes = Polygons([Box(0, 0, 1)])
        BoxEdit(source=boxes)
        plot = bokeh_server_renderer.get_plot(boxes)
        self.assertEqual(plot.handles['rect_source']._callbacks,
                         {'data': [plot.callbacks[0].on_change]})

    def test_box_edit_callback_initialized_js(self):
        boxes = Polygons([Box(0, 0, 1)])
        BoxEdit(source=boxes)
        plot = bokeh_renderer.get_plot(boxes)
        self.assertEqual(plot.handles['rect_source'].js_property_callbacks,
                         {'change:data': [plot.callbacks[0].callbacks[0]]})

    def test_poly_edit_callback(self):
        polys = Polygons([[(0, 0), (2, 2), (4, 0)]])
        poly_edit = PolyEdit(source=polys)
        plot = bokeh_server_renderer.get_plot(polys)
        self.assertIsInstance(plot.callbacks[0], PolyEditCallback)
        callback = plot.callbacks[0]
        data = {'x': [[1, 2, 3], [3, 4, 5]], 'y': [[1, 2, 3], [3, 4, 5]]}
        callback.on_msg({'data': data})
        element = Polygons([[(1, 1), (2, 2), (3, 3)], [(3, 3), (4, 4), (5, 5)]])
        self.assertEqual(poly_edit.element, element)

    def test_poly_edit_callback_initialized_server(self):
        polys = Polygons([[(0, 0), (2, 2), (4, 0)]])
        PolyEdit(source=polys)
        plot = bokeh_server_renderer.get_plot(polys)
        self.assertEqual(plot.handles['source']._callbacks,
                         {'data': [plot.callbacks[0].on_change]})

    def test_poly_edit_callback_initialized_js(self):
        polys = Polygons([[(0, 0), (2, 2), (4, 0)]])
        PolyEdit(source=polys)
        plot = bokeh_renderer.get_plot(polys)
        self.assertEqual(plot.handles['source'].js_property_callbacks,
                         {'change:data': [plot.callbacks[0].callbacks[0]]})

    def test_poly_edit_shared_callback(self):
        polys = Polygons([[(0, 0), (2, 2), (4, 0)]])
        polys2 = Polygons([[(0, 0), (2, 2), (4, 0)]])
        poly_edit = PolyEdit(source=polys, shared=True)
        poly_edit2 = PolyEdit(source=polys2, shared=True)
        plot = bokeh_server_renderer.get_plot(polys*polys2)
        edit_tools = [t for t in plot.state.tools if isinstance(t, PolyEditTool)]
        self.assertEqual(len(edit_tools), 1)
        plot1, plot2 = plot.subplots.values()
        self.assertIsInstance(plot1.callbacks[0], PolyEditCallback)
        callback = plot1.callbacks[0]
        data = {'x': [[1, 2, 3], [3, 4, 5]], 'y': [[1, 2, 3], [3, 4, 5]]}
        callback.on_msg({'data': data})
        self.assertIsInstance(plot2.callbacks[0], PolyEditCallback)
        callback = plot2.callbacks[0]
        data = {'x': [[1, 2, 3], [3, 4, 5]], 'y': [[1, 2, 3], [3, 4, 5]]}
        callback.on_msg({'data': data})
        element = Polygons([[(1, 1), (2, 2), (3, 3)], [(3, 3), (4, 4), (5, 5)]])
        self.assertEqual(poly_edit.element, element)
        self.assertEqual(poly_edit2.element, element)

    def test_point_draw_shared_datasource_callback(self):
        points = Points([1, 2, 3])
        table = Table(points.data, ['x', 'y'])
        layout = (points + table).options(shared_datasource=True, clone=False)
        PointDraw(source=points)
        self.assertIs(points.data, table.data)
        plot = bokeh_renderer.get_plot(layout)
        point_plot = plot.subplots[(0, 0)].subplots['main']
        table_plot = plot.subplots[(0, 1)].subplots['main']
        self.assertIs(point_plot.handles['source'], table_plot.handles['source'])
        self.assertIn(plot.id, point_plot.callbacks[0].callbacks[0].code)
        self.assertNotIn('PLACEHOLDER_PLOT_ID', point_plot.callbacks[0].callbacks[0].code)
