##Copyright 2018-2024 Thomas Paviot (tpaviot@gmail.com)
##
##This file is part of pythonOCC.
##
##pythonOCC is free software: you can redistribute it and/or modify
##it under the terms of the GNU Lesser General Public License as published by
##the Free Software Foundation, either version 3 of the License, or
##(at your option) any later version.
##
##pythonOCC is distributed in the hope that it will be useful,
##but WITHOUT ANY WARRANTY; without even the implied warranty of
##MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##GNU Lesser General Public License for more details.
##
##You should have received a copy of the GNU Lesser General Public License
##along with pythonOCC.  If not, see <http://www.gnu.org/licenses/>.

import os
from typing import Union, List

from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Edge, TopoDS_Shape
from OCC.Core.BRepTools import breptools
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.StlAPI import stlapi, StlAPI_Writer
from OCC.Core.BRep import BRep_Builder
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Pnt2d
from OCC.Core.Bnd import Bnd_Box2d
from OCC.Core.IGESControl import (
    IGESControl_Controller,
    IGESControl_Reader,
    IGESControl_Writer,
)
from OCC.Core.STEPControl import (
    STEPControl_Reader,
    STEPControl_Writer,
    STEPControl_AsIs,
)
from OCC.Core.Interface import Interface_Static
from OCC.Core.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFDoc import (
    XCAFDoc_DocumentTool,
    XCAFDoc_ColorTool,
)
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDF import TDF_LabelSequence, TDF_Label
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.TColStd import TColStd_IndexedDataMapOfStringString
from OCC.Core.TCollection import TCollection_AsciiString
from OCC.Core.RWPly import RWPly_CafWriter
from OCC.Core.Message import Message_ProgressRange

from OCC.Core.RWGltf import RWGltf_CafReader, RWGltf_CafWriter
from OCC.Core.RWObj import RWObj_CafWriter
from OCC.Core.RWMesh import (
    RWMesh_CoordinateSystem_posYfwd_posZup,
    RWMesh_CoordinateSystem_negZfwd_posYup,
)
from OCC.Core.UnitsMethods import unitsmethods

from OCC.Extend.TopologyUtils import discretize_edge, get_sorted_hlr_edges

try:
    import svgwrite

    HAVE_SVGWRITE = True
except ImportError:
    HAVE_SVGWRITE = False


def check_svgwrite_installed():
    if not HAVE_SVGWRITE:
        raise IOError(
            "svg exporter not available because the svgwrite package is not installed. use $pip install svgwrite'"
        )


##########################
# Step import and export #
##########################
def read_step_file(
    filename: str, as_compound: bool = True, verbosity: bool = False
) -> Union[TopoDS_Shape, List[TopoDS_Shape]]:
    """Read a STEP file and return the contained shape(s).

    Args:
        filename: Path to the STEP file to read
        as_compound: If True, combine multiple shapes into a single compound.
                    Defaults to True.
        verbosity: If True, print detailed information during import.
                  Defaults to False.

    Returns:
        Either a single TopoDS_Shape (if as_compound=True or only one shape present)
        or a list of TopoDS_Shape objects

    Raises:
        FileNotFoundError: If the specified file does not exist
        AssertionError: If there are errors during STEP file reading or conversion
    """
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"STEP file not found: {filename}")

    step_reader = STEPControl_Reader()
    status = step_reader.ReadFile(filename)

    if status != IFSelect_RetDone:
        raise AssertionError("Error: can't read file.")

    if verbosity:
        step_reader.PrintCheckLoad(False, IFSelect_ItemsByEntity)
        step_reader.PrintCheckTransfer(False, IFSelect_ItemsByEntity)

    transfer_result = step_reader.TransferRoots()
    if not transfer_result:
        raise AssertionError("Transfer failed.")

    nb_shapes = step_reader.NbShapes()
    if nb_shapes == 0:
        raise AssertionError("No shape to transfer.")

    if nb_shapes == 1:
        if as_compound:
            return step_reader.Shape(1)

        return [step_reader.Shape(1)]

    shapes = []
    for i in range(1, nb_shapes + 1):
        shape = step_reader.Shape(i)
        if not shape.IsNull():
            shapes.append(shape)

    if as_compound:
        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for shape in shapes:
            builder.Add(compound, shape)
        return compound

    return shapes


def write_step_file(
    shape: TopoDS_Shape, filename: str, application_protocol: str = "AP203"
) -> None:
    """Export a shape to STEP format.

    Args:
        shape: The shape to export
        filename: Target STEP file path
        application_protocol: STEP format version to use.
                            Can be "AP203" (basic geometry), "AP214IS" (colors and layers),
                            or "AP242DIS" (latest version with PMI support).
                            Defaults to "AP203".

    Raises:
        AssertionError: If shape is null or protocol is invalid
        IOError: If export fails
    """
    if shape.IsNull():
        raise AssertionError("Shape is null.")

    if application_protocol not in ["AP203", "AP214IS", "AP242DIS"]:
        raise AssertionError(
            f"application_protocol must be either AP203 or AP214IS. You passed {application_protocol}."
        )

    if os.path.isfile(filename):
        print(f"Warning: {filename} file already exists and will be replaced")

    # Initialize STEP writer
    writer = STEPControl_Writer()
    Interface_Static.SetCVal("write.step.schema", application_protocol)

    # Convert and write shape
    writer.Transfer(shape, STEPControl_AsIs)
    status = writer.Write(filename)

    if status != IFSelect_RetDone:
        raise IOError("Error while writing shape to STEP file.")
    if not os.path.isfile(filename):
        raise IOError(f"{filename} not saved to filesystem.")


def read_step_file_with_names_colors(filename: str):
    """Returns list of tuples (topods_shape, label, color)
    Use OCAF.
    """
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"{filename} not found.")
    # the list:
    output_shapes = {}

    # create an handle to a document
    doc = TDocStd_Document("pythonocc-doc-step-import")

    # Get root assembly
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool(doc.Main())
    # layer_tool = XCAFDoc_DocumentTool_LayerTool(doc.Main())
    # mat_tool = XCAFDoc_DocumentTool_MaterialTool(doc.Main())

    step_reader = STEPCAFControl_Reader()
    step_reader.SetColorMode(True)
    step_reader.SetLayerMode(True)
    step_reader.SetNameMode(True)
    step_reader.SetMatMode(True)
    step_reader.SetGDTMode(True)

    status = step_reader.ReadFile(filename)
    if status == IFSelect_RetDone:
        step_reader.Transfer(doc)

    locs = []

    def _get_sub_shapes(lab, loc):
        l_subss = TDF_LabelSequence()
        shape_tool.GetSubShapes(lab, l_subss)
        # print("Nb subshapes   :", l_subss.Length())
        l_comps = TDF_LabelSequence()
        shape_tool.GetComponents(lab, l_comps)

        name = lab.GetLabelName()
        print("Name :", name)

        if shape_tool.IsAssembly(lab):
            l_c = TDF_LabelSequence()
            shape_tool.GetComponents(lab, l_c)
            for i in range(l_c.Length()):
                label = l_c.Value(i + 1)
                if shape_tool.IsReference(label):
                    # print("\n########  reference label :", label)
                    label_reference = TDF_Label()
                    shape_tool.GetReferredShape(label, label_reference)
                    loc = shape_tool.GetLocation(label)
                    locs.append(loc)
                    _get_sub_shapes(label_reference, loc)
                    locs.pop()

        elif shape_tool.IsSimpleShape(lab):
            # print("\n########  simpleshape label :", lab)
            shape = shape_tool.GetShape(lab)
            # print("    all ass locs   :", locs)

            loc = TopLoc_Location()
            for location in locs:
                loc = loc.Multiplied(location)

            c = Quantity_Color(0.5, 0.5, 0.5, Quantity_TOC_RGB)  # default color
            color_set = False
            if (
                color_tool.GetInstanceColor(shape, 0, c)
                or color_tool.GetInstanceColor(shape, 1, c)
                or color_tool.GetInstanceColor(shape, 2, c)
            ):
                color_tool.SetInstanceColor(shape, 0, c)
                color_tool.SetInstanceColor(shape, 1, c)
                color_tool.SetInstanceColor(shape, 2, c)
                color_set = True
                n = c.Name(c.Red(), c.Green(), c.Blue())
                print(
                    "    instance color Name & RGB: ",
                    c,
                    n,
                    c.Red(),
                    c.Green(),
                    c.Blue(),
                )

            if not color_set:
                if (
                    XCAFDoc_ColorTool.GetColor(lab, 0, c)
                    or XCAFDoc_ColorTool.GetColor(lab, 1, c)
                    or XCAFDoc_ColorTool.GetColor(lab, 2, c)
                ):
                    color_tool.SetInstanceColor(shape, 0, c)
                    color_tool.SetInstanceColor(shape, 1, c)
                    color_tool.SetInstanceColor(shape, 2, c)

                    n = c.Name(c.Red(), c.Green(), c.Blue())
                    print(
                        "    shape color Name & RGB: ",
                        c,
                        n,
                        c.Red(),
                        c.Green(),
                        c.Blue(),
                    )

            shape_disp = BRepBuilderAPI_Transform(shape, loc.Transformation()).Shape()
            if shape_disp not in output_shapes:
                output_shapes[shape_disp] = [lab.GetLabelName(), c]
            for i in range(l_subss.Length()):
                lab_subs = l_subss.Value(i + 1)
                # print("\n########  simpleshape subshape label :", lab)
                shape_sub = shape_tool.GetShape(lab_subs)

                c = Quantity_Color(0.5, 0.5, 0.5, Quantity_TOC_RGB)  # default color
                color_set = False
                if (
                    color_tool.GetInstanceColor(shape_sub, 0, c)
                    or color_tool.GetInstanceColor(shape_sub, 1, c)
                    or color_tool.GetInstanceColor(shape_sub, 2, c)
                ):
                    color_tool.SetInstanceColor(shape_sub, 0, c)
                    color_tool.SetInstanceColor(shape_sub, 1, c)
                    color_tool.SetInstanceColor(shape_sub, 2, c)
                    color_set = True
                    n = c.Name(c.Red(), c.Green(), c.Blue())
                    print(
                        "    instance color Name & RGB: ",
                        c,
                        n,
                        c.Red(),
                        c.Green(),
                        c.Blue(),
                    )

                if not color_set:
                    if (
                        XCAFDoc_ColorTool.GetColor(lab_subs, 0, c)
                        or XCAFDoc_ColorTool.GetColor(lab_subs, 1, c)
                        or XCAFDoc_ColorTool.GetColor(lab_subs, 2, c)
                    ):
                        color_tool.SetInstanceColor(shape, 0, c)
                        color_tool.SetInstanceColor(shape, 1, c)
                        color_tool.SetInstanceColor(shape, 2, c)

                        n = c.Name(c.Red(), c.Green(), c.Blue())
                        print(
                            "    shape color Name & RGB: ",
                            c,
                            n,
                            c.Red(),
                            c.Green(),
                            c.Blue(),
                        )
                shape_to_disp = BRepBuilderAPI_Transform(
                    shape_sub, loc.Transformation()
                ).Shape()
                # position the subshape to display
                if shape_to_disp not in output_shapes:
                    output_shapes[shape_to_disp] = [lab_subs.GetLabelName(), c]

    def _get_shapes():
        labels = TDF_LabelSequence()
        shape_tool.GetFreeShapes(labels)
        print("Number of shapes at root :", labels.Length())
        for i in range(labels.Length()):
            root_item = labels.Value(i + 1)
            _get_sub_shapes(root_item, None)

    _get_shapes()
    return output_shapes


#########################
# STL import and export #
#########################
def write_stl_file(
    shape: TopoDS_Shape,
    filename: str,
    mode: str = "ascii",
    linear_deflection: float = 0.9,
    angular_deflection: float = 0.5,
) -> None:
    """Export a shape to STL format.

    The shape is first meshed using the specified deflection parameters before export.

    Args:
        shape: The shape to export
        filename: Target STL file path
        mode: Export format, either "ascii" or "binary".
              Defaults to "ascii".
        linear_deflection: Maximum distance between mesh and actual surface.
                          Lower values produce more accurate but larger meshes.
                          Defaults to 0.9
        angular_deflection: Maximum angle between mesh elements in radians.
                          Lower values produce smoother meshes.
                          Defaults to 0.5

    Raises:
        AssertionError: If shape is null or meshing fails
        IOError: If export fails
    """
    if shape.IsNull():
        raise AssertionError("Shape is null.")

    if mode not in ["ascii", "binary"]:
        raise AssertionError("mode should be either ascii or binary")

    if os.path.isfile(filename):
        print(f"Warning: {filename} already exists and will be replaced")

    # Mesh the shape
    mesh = BRepMesh_IncrementalMesh(
        shape, linear_deflection, False, angular_deflection, True
    )
    mesh.Perform()
    if not mesh.IsDone():
        raise AssertionError("Mesh is not done.")

    # Export to STL
    writer = StlAPI_Writer()
    writer.SetASCIIMode(mode == "ascii")
    writer.Write(shape, filename)

    if not os.path.isfile(filename):
        raise IOError("File not written to disk.")


def read_stl_file(filename: str):
    """open a stl file, reads the content, and returns a BRep topods_shape object"""
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"{filename} not found.")

    the_shape = TopoDS_Shape()
    stlapi.Read(the_shape, filename)

    if the_shape.IsNull():
        raise AssertionError("Shape is null.")

    return the_shape


######################
# IGES import/export #
######################
def read_iges_file(
    filename: str,
    return_as_shapes: bool = False,
    verbosity: bool = False,
    visible_only: bool = False,
):
    """read the IGES file and returns a compound
    filename: the file path
    return_as_shapes: optional, False by default. If True returns a list of shapes,
                      else returns a single compound
    verbosity: optionl, False by default.
    """
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"{filename} not found.")

    IGESControl_Controller.Init()

    iges_reader = IGESControl_Reader()
    iges_reader.SetReadVisible(visible_only)
    status = iges_reader.ReadFile(filename)

    if status != IFSelect_RetDone:  # check status
        raise IOError("Cannot read IGES file")

    if verbosity:
        failsonly = False
        iges_reader.PrintCheckLoad(failsonly, IFSelect_ItemsByEntity)
        iges_reader.PrintCheckTransfer(failsonly, IFSelect_ItemsByEntity)
    iges_reader.ClearShapes()
    iges_reader.TransferRoots()
    nbr = iges_reader.NbShapes()

    _shapes = []
    for i in range(1, nbr + 1):
        a_shp = iges_reader.Shape(i)
        if not a_shp.IsNull():
            _shapes.append(a_shp)

    # create a compound and store all shapes
    if not return_as_shapes:
        builder = BRep_Builder()
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)
        for s in _shapes:
            builder.Add(compound, s)
        return [compound]

    return _shapes


def write_iges_file(a_shape: TopoDS_Shape, filename: str):
    """exports a shape to a STEP file
    a_shape: the topods_shape to export (a compound, a solid etc.)
    filename: the filename
    application protocol: "AP203" or "AP214"
    """
    # a few checks
    if a_shape.IsNull():
        raise AssertionError("Shape is null.")
    if os.path.isfile(filename):
        print(f"Warning: {filename} already exists and will be replaced")
    # create and initialize the step exporter
    iges_writer = IGESControl_Writer()
    iges_writer.AddShape(a_shape)
    status = iges_writer.Write(filename)

    if status != IFSelect_RetDone:
        raise AssertionError("Not done.")
    if not os.path.isfile(filename):
        raise IOError("File not written to disk.")


##############
# SVG export #
##############
def edge_to_svg_polyline(topods_edge: TopoDS_Edge, tol: float = 0.1, unit: str = "mm"):
    """Returns a svgwrite.Path for the edge, and the 2d bounding box"""
    check_svgwrite_installed()

    unit_factor = 1  # by default

    if unit == "mm":
        unit_factor = 1
    elif unit == "m":
        unit_factor = 1e3

    points_3d = discretize_edge(topods_edge, tol)
    points_2d = []
    box2d = Bnd_Box2d()

    for point in points_3d:
        # we tak only the first 2 coordinates (x and y, leave z)
        x_p = -point[0] * unit_factor
        y_p = point[1] * unit_factor
        box2d.Add(gp_Pnt2d(x_p, y_p))
        points_2d.append((x_p, y_p))

    return svgwrite.shapes.Polyline(points_2d, fill="none"), box2d


def export_shape_to_svg(
    shape: TopoDS_Shape,
    filename: str = None,
    width: int = 800,
    height: int = 600,
    margin_left: int = 10,
    margin_top: int = 30,
    export_hidden_edges: bool = True,
    location: gp_Pnt = gp_Pnt(0, 0, 0),
    direction: gp_Dir = gp_Dir(1, 1, 1),
    color: str = "black",
    line_width: str = "1px",
    unit: str = "mm",
):
    """export a single shape to an svg file and/or string.
    shape: the TopoDS_Shape to export
    filename (optional): if provided, save to an svg file
    width, height (optional): integers, specify the canvas size in pixels
    margin_left, margin_top (optional): integers, in pixel
    export_hidden_edges (optional): whether or not draw hidden edges using a dashed line
    location (optional): a gp_Pnt, the lookat
    direction (optional): to set up the projector direction
    color (optional), "default to "black".
    line_width (optional, default to 1): an integer
    """
    check_svgwrite_installed()

    if shape.IsNull():
        raise AssertionError("shape is Null")

    # find all edges
    visible_edges, hidden_edges = get_sorted_hlr_edges(
        shape,
        position=location,
        direction=direction,
        export_hidden_edges=export_hidden_edges,
    )

    # compute polylines for all edges
    # we compute a global 2d bounding box as well, to be able to compute
    # the scale factor and translation vector to apply to all 2d edges so that
    # they fit the svg canva
    global_2d_bounding_box = Bnd_Box2d()

    polylines = []
    for visible_edge in visible_edges:
        visible_svg_line, visible_edge_box2d = edge_to_svg_polyline(
            visible_edge, 0.1, unit
        )
        polylines.append(visible_svg_line)
        global_2d_bounding_box.Add(visible_edge_box2d)
    if export_hidden_edges:
        for hidden_edge in hidden_edges:
            hidden_svg_line, hidden_edge_box2d = edge_to_svg_polyline(
                hidden_edge, 0.1, unit
            )
            # hidden lines are dashed style
            hidden_svg_line.dasharray([5, 5])
            polylines.append(hidden_svg_line)
            global_2d_bounding_box.Add(hidden_edge_box2d)

    # translate and scale polylines

    # first compute shape translation and scale according to size/margins
    x_min, y_min, x_max, y_max = global_2d_bounding_box.Get()
    bb2d_width = x_max - x_min
    bb2d_height = y_max - y_min

    # build the svg drawing
    dwg = svgwrite.Drawing(filename, (width, height), debug=True)
    # adjust the view box so that the lines fit then svg canvas
    dwg.viewbox(
        x_min - margin_left,
        y_min - margin_top,
        bb2d_width + 2 * margin_left,
        bb2d_height + 2 * margin_top,
    )

    for polyline in polylines:
        # apply color and style
        polyline.stroke(color, width=line_width, linecap="round")
        # then adds the polyline to the svg canva
        dwg.add(polyline)

    # export to string or file according to the user choice
    if filename is not None:
        dwg.save()
        if not os.path.isfile(filename):
            raise AssertionError("svg export failed")
        print(f"Shape successfully exported to {filename}")
        return True
    return dwg.tostring()


#################################################
# ply export (write not avaiable from upstream) #
#################################################
def write_ply_file(a_shape: TopoDS_Shape, ply_filename: str):
    """ocaf based ply exporter"""
    # create a document
    doc = TDocStd_Document("pythonocc-doc-ply-export")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())

    # mesh shape
    breptools.Clean(a_shape)
    msh_algo = BRepMesh_IncrementalMesh(a_shape, True)
    msh_algo.Perform()

    shape_tool.AddShape(a_shape)

    # metadata
    a_file_info = TColStd_IndexedDataMapOfStringString()
    a_file_info.Add(
        TCollection_AsciiString("Authors"), TCollection_AsciiString("pythonocc")
    )

    rwply_writer = RWPly_CafWriter(ply_filename)

    rwply_writer.SetNormals(True)
    rwply_writer.SetColors(True)
    rwply_writer.SetTexCoords(True)
    rwply_writer.SetPartId(True)
    rwply_writer.SetFaceId(True)

    rwply_writer.Perform(doc, a_file_info, Message_ProgressRange())


#################################################
# Obj export (write not avaiable from upstream) #
#################################################
def write_obj_file(a_shape: TopoDS_Shape, obj_filename: str):
    """ocaf based ply exporter"""
    # create a document
    doc = TDocStd_Document("pythonocc-doc-obj-export")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())

    # mesh shape
    breptools.Clean(a_shape)
    msh_algo = BRepMesh_IncrementalMesh(a_shape, True)
    msh_algo.Perform()

    shape_tool.AddShape(a_shape)

    # metadata
    a_file_info = TColStd_IndexedDataMapOfStringString()
    a_file_info.Add(
        TCollection_AsciiString("Authors"), TCollection_AsciiString("pythonocc")
    )

    rwobj_writer = RWObj_CafWriter(obj_filename)

    # apply a scale factor of 0.001 to mimic conversion from m to mm
    csc = rwobj_writer.ChangeCoordinateSystemConverter()

    system_unit_factor = unitsmethods.GetCasCadeLengthUnit() * 0.001
    csc.SetInputLengthUnit(system_unit_factor)
    csc.SetOutputLengthUnit(system_unit_factor)
    csc.SetInputCoordinateSystem(RWMesh_CoordinateSystem_posYfwd_posZup)
    csc.SetOutputCoordinateSystem(RWMesh_CoordinateSystem_negZfwd_posYup)

    rwobj_writer.SetCoordinateSystemConverter(csc)

    rwobj_writer.Perform(doc, a_file_info, Message_ProgressRange())


########
# gltf #
########
def read_gltf_file(
    filename: str,
    is_parallel: bool = False,
    is_double_precision: bool = False,
    skip_late_data_loading: bool = False,
    keep_late_data: bool = True,
    verbose: bool = False,
    load_all_scenes: bool = False,
):
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"{filename} not found.")

    gltf_reader = RWGltf_CafReader()
    gltf_reader.SetSystemCoordinateSystem(RWMesh_CoordinateSystem_posYfwd_posZup)
    gltf_reader.SetParallel(is_parallel)
    gltf_reader.SetDoublePrecision(is_double_precision)
    gltf_reader.SetToSkipLateDataLoading(skip_late_data_loading)
    gltf_reader.SetToKeepLateData(keep_late_data)
    gltf_reader.SetToPrintDebugMessages(verbose)
    gltf_reader.SetLoadAllScenes(load_all_scenes)

    status = gltf_reader.Perform(filename, Message_ProgressRange())

    if status != IFSelect_RetDone:
        raise IOError("Error while reading GLTF file.")

    return [gltf_reader.SingleShape()]


def write_gltf_file(a_shape: TopoDS_Shape, gltf_filename: str, binary=True):
    """ocaf based ply exporter"""
    # create a document
    doc = TDocStd_Document("pythonocc-doc-gltf-export")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())

    # mesh shape
    breptools.Clean(a_shape)
    msh_algo = BRepMesh_IncrementalMesh(a_shape, True)
    msh_algo.Perform()

    shape_tool.AddShape(a_shape)

    # metadata
    a_file_info = TColStd_IndexedDataMapOfStringString()
    a_file_info.Add(
        TCollection_AsciiString("Authors"), TCollection_AsciiString("pythonocc")
    )

    rwgltf_writer = RWGltf_CafWriter(gltf_filename, binary)

    status = rwgltf_writer.Perform(doc, a_file_info, Message_ProgressRange())

    if status != IFSelect_RetDone:
        raise IOError("Error while writing shape to GLTF file.")
