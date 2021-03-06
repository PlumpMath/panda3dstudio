from ...base import *


class GeomTransformBase(BaseObject):

    def __init__(self):

        self._verts_to_transf = {"vert": {}, "edge": {}, "poly": {}}
        self._rows_to_transf = {"vert": None, "edge": None, "poly": None, "normal": None}
        self._transf_start_data = {"bounds": None, "pos_array": None}
        self._pos_arrays = {"main": None, "edge": None}
        self._transformed_verts = set()

    def _update_verts_to_transform(self, subobj_lvl):

        selected_subobj_ids = self._selected_subobj_ids[subobj_lvl]
        self._rows_to_transf[subobj_lvl] = rows_to_transf = SparseArray.allOff()

        if subobj_lvl != "normal":
            self._verts_to_transf[subobj_lvl] = verts_to_transf = {}

        merged_verts = self._merged_verts
        merged_verts_to_transf = set()

        if subobj_lvl == "vert":

            for vert_id in selected_subobj_ids:
                merged_verts_to_transf.add(merged_verts[vert_id])

        elif subobj_lvl == "edge":

            edges = self._subobjs["edge"]

            for edge_id in selected_subobj_ids:

                edge = edges[edge_id]

                for vert_id in edge:
                    merged_verts_to_transf.add(merged_verts[vert_id])

        elif subobj_lvl == "poly":

            polys = self._subobjs["poly"]

            for poly_id in selected_subobj_ids:

                poly = polys[poly_id]

                for vert_ids in poly:
                    for vert_id in vert_ids:
                        merged_verts_to_transf.add(merged_verts[vert_id])

        elif subobj_lvl == "normal":

            verts = self._subobjs["vert"]

            for vert_id in selected_subobj_ids:
                vert = verts[vert_id]
                rows_to_transf.set_bit(vert.get_row_index())

            return

        for merged_vert in merged_verts_to_transf:

            rows = merged_vert.get_row_indices()
            verts_to_transf[merged_vert] = rows

            for row in rows:
                rows_to_transf.set_bit(row)

    def _get_ref_node(self):

        if GlobalData["coord_sys_type"] == "local":
            return self.get_toplevel_object().get_pivot()
        else:
            return Mgr.get(("grid", "origin"))

    def _get_transf_center_pos(self):

        cs_type = GlobalData["coord_sys_type"]
        tc_type = GlobalData["transf_center_type"]

        if tc_type == "pivot" or (cs_type == "local" and tc_type == "cs_origin"):
            return self.get_toplevel_object().get_pivot().get_pos(self.world)
        else:
            return Mgr.get("transf_center_pos")

    def update_vertex_positions(self, vertex_ids):

        verts = self._subobjs["vert"]
        polys = self._subobjs["poly"]
        merged_verts = self._merged_verts
        polys_to_update = set()
        verts_to_resmooth = set()
        geom_node_top = self._toplvl_node
        vertex_data_top = geom_node_top.modify_geom(0).modify_vertex_data()
        pos_writer = GeomVertexWriter(vertex_data_top, "vertex")

        for vert_id in vertex_ids:
            vert = verts[vert_id]
            poly = polys[vert.get_polygon_id()]
            polys_to_update.add(poly)
            row = vert.get_row_index()
            pos = vert.get_pos()
            pos_writer.set_row(row)
            pos_writer.set_data3f(pos)

        pos_array = vertex_data_top.get_array(0)

        for geom_type in ("poly", "poly_picking"):
            vertex_data = self._vertex_data[geom_type]
            vertex_data.set_array(0, pos_array)

        geoms = self._geoms

        for geom_type in ("vert", "normal"):
            vertex_data = geoms[geom_type]["pickable"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, pos_array)
            vertex_data = geoms[geom_type]["sel_state"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, pos_array)

        pos_array = GeomVertexArrayData(pos_array)
        handle = pos_array.modify_handle()
        handle.set_data(handle.get_data() * 2)
        vertex_data = geoms["edge"]["pickable"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, pos_array)
        vertex_data = geoms["edge"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, pos_array)

        for poly in polys_to_update:
            poly.update_center_pos()
            poly.update_normal()
            verts_to_resmooth.update(merged_verts[v_id] for v_id in poly.get_vertex_ids())

        self.update_vertex_normals(verts_to_resmooth)

        bounds = geom_node_top.get_bounds()
        self._origin.node().set_bounds(bounds)
        model = self.get_toplevel_object()
        model.get_bbox().update(*self._origin.get_tight_bounds())

    def reposition_vertices(self, computation):
        """ Change the positions of all vertices using the given computation """

        verts = self._subobjs["vert"]
        geoms = self._geoms
        geom_node_top = self._toplvl_node
        vertex_data_top = geom_node_top.modify_geom(0).modify_vertex_data()
        pos_writer = GeomVertexWriter(vertex_data_top, "vertex")

        for vert in self._subobjs["vert"].itervalues():
            row = vert.get_row_index()
            old_pos = vert.get_initial_pos()
            new_pos = computation(Point3(*old_pos))
            pos_writer.set_row(row)
            pos_writer.set_data3f(Point3(*new_pos))
            vert.set_pos(Point3(*new_pos))

        array = vertex_data_top.get_array(0)

        for geom_type in ("poly", "poly_picking"):
            vertex_data = self._vertex_data[geom_type]
            vertex_data.set_array(0, array)

        for geom_type in ("vert", "normal"):
            vertex_data = geoms[geom_type]["pickable"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, array)
            vertex_data = geoms[geom_type]["sel_state"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, array)

        array = GeomVertexArrayData(array)
        handle = array.modify_handle()
        handle.set_data(handle.get_data() * 2)
        vertex_data = geoms["edge"]["pickable"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, array)
        vertex_data = geoms["edge"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, array)

        self.update_poly_centers()
        self.update_poly_normals()

        self.get_toplevel_object().get_bbox().update(*self._origin.get_tight_bounds())

    def bake_transform(self):
        """ Bake the origin's transform into the vertices and reset it to identity """

        mat = self._origin.get_mat()
        geoms = self._geoms
        geom_node_top = self._toplvl_node
        geom_node_top.modify_geom(0).transform_vertices(mat)
        self._origin.clear_transform()
        vertex_data_top = geom_node_top.get_geom(0).get_vertex_data()
        array = vertex_data_top.get_array(0)

        for geom_type in ("poly", "poly_picking"):
            vertex_data = self._vertex_data[geom_type]
            vertex_data.set_array(0, array)

        for geom_type in ("vert", "normal"):
            vertex_data = geoms[geom_type]["pickable"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, array)
            vertex_data = geoms[geom_type]["sel_state"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, array)

        array = GeomVertexArrayData(array)
        handle = array.modify_handle()
        handle.set_data(handle.get_data() * 2)
        vertex_data = geoms["edge"]["pickable"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, array)
        vertex_data = geoms["edge"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, array)

        pos_reader = GeomVertexReader(vertex_data_top, "vertex")

        for vert in self._subobjs["vert"].itervalues():
            row = vert.get_row_index()
            pos_reader.set_row(row)
            pos = pos_reader.get_data3f()
            # NOTE: the LVecBase3f returned by the GeomVertexReader is a const
            vert.set_pos(Point3(*pos))

        self.update_poly_centers()
        self.update_poly_normals()

        self.get_toplevel_object().get_bbox().update(*self._origin.get_tight_bounds())

    def init_transform(self):

        geom_node_top = self._toplvl_node
        start_data = self._transf_start_data
        start_data["bounds"] = geom_node_top.get_bounds()
        pos_array = geom_node_top.modify_geom(0).modify_vertex_data().modify_array(0)
        start_data["pos_array"] = GeomVertexArrayData(pos_array)

        for geom_type in ("poly", "poly_picking"):
            vertex_data = self._vertex_data[geom_type]
            vertex_data.set_array(0, pos_array)

        geoms = self._geoms

        vertex_data = geoms["vert"]["pickable"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, pos_array)
        vertex_data = geoms["vert"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, pos_array)
        self._pos_arrays["main"] = pos_array

        pos_array = GeomVertexArrayData(pos_array)
        handle = pos_array.modify_handle()
        handle.set_data(handle.get_data() * 2)
        vertex_data = geoms["edge"]["pickable"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, pos_array)
        vertex_data = geoms["edge"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, pos_array)
        self._pos_arrays["edge"] = pos_array

    def set_vert_sel_coordinate(self, axis, value):

        verts = self._verts_to_transf["vert"]

        if not verts:
            return

        origin = self._origin
        ref_node = self._get_ref_node()
        vertex_data_top = self._toplvl_node.modify_geom(0).modify_vertex_data()
        tmp_vertex_data = GeomVertexData(vertex_data_top)
        index = "xyz".index(axis)
        pos_rewriter = GeomVertexRewriter(tmp_vertex_data, "vertex")

        for rows in verts.itervalues():
            for row in rows:
                pos_rewriter.set_row(row)
                pos = pos_rewriter.get_data3f()
                pos = ref_node.get_relative_point(origin, pos)
                pos[index] = value
                pos = origin.get_relative_point(ref_node, pos)
                pos_rewriter.set_data3f(pos)

        pos_array = GeomVertexArrayData(tmp_vertex_data.get_array(0))
        vertex_data_top.set_array(0, pos_array)

        handle = self._pos_arrays["main"].modify_handle()
        data = pos_array.get_handle().get_data()
        handle.set_data(data)

        handle = self._pos_arrays["edge"].modify_handle()
        handle.set_data(data * 2)

    def transform_selection(self, subobj_lvl, transf_type, value):

        rows = self._rows_to_transf[subobj_lvl]

        if not rows:
            return

        ref_node = self._get_ref_node()
        transf_center_pos = self._get_transf_center_pos()
        vertex_data_top = self._toplvl_node.modify_geom(0).modify_vertex_data()
        tmp_vertex_data = GeomVertexData(vertex_data_top)
        tmp_vertex_data.set_array(0, GeomVertexArrayData(self._transf_start_data["pos_array"]))

        if transf_type == "translate":

            vec = self._origin.get_relative_vector(ref_node, value)
            mat = Mat4.translate_mat(vec)

        elif transf_type == "rotate":

            tc_pos = self._origin.get_relative_point(self.world, transf_center_pos)
            quat = self._origin.get_quat(ref_node) * value * ref_node.get_quat(self._origin)
            quat_mat = Mat4()
            quat.extract_to_matrix(quat_mat)
            offset_mat = Mat4.translate_mat(-tc_pos)
            mat = offset_mat * quat_mat
            offset_mat = Mat4.translate_mat(tc_pos)
            mat *= offset_mat

        elif transf_type == "scale":

            tc_pos = self._origin.get_relative_point(self.world, transf_center_pos)
            scale_mat = Mat4.scale_mat(value)
            mat = self._origin.get_mat(ref_node) * scale_mat * ref_node.get_mat(self._origin)
            # remove translation component
            mat.set_row(3, VBase3())
            offset_mat = Mat4.translate_mat(-tc_pos)
            mat = offset_mat * mat
            offset_mat = Mat4.translate_mat(tc_pos)
            mat *= offset_mat

        tmp_vertex_data.transform_vertices(mat, rows)
        pos_array = GeomVertexArrayData(tmp_vertex_data.get_array(0))
        vertex_data_top.set_array(0, pos_array)

        handle = self._pos_arrays["main"].modify_handle()
        data = pos_array.get_handle().get_data()
        handle.set_data(data)

        handle = self._pos_arrays["edge"].modify_handle()
        handle.set_data(data * 2)

    def finalize_transform(self, cancelled=False):

        start_data = self._transf_start_data
        geom_node_top = self._toplvl_node
        vertex_data_top = geom_node_top.modify_geom(0).modify_vertex_data()

        if cancelled:

            bounds = start_data["bounds"]

            pos_array = start_data["pos_array"]
            vertex_data_top.set_array(0, pos_array)

            for geom_type in ("poly", "poly_picking"):
                self._vertex_data[geom_type].set_array(0, pos_array)

            handle = self._pos_arrays["main"].modify_handle()
            data = pos_array.get_handle().get_data()
            handle.set_data(data)

            handle = self._pos_arrays["edge"].modify_handle()
            handle.set_data(data * 2)

        else:

            bounds = geom_node_top.get_bounds()

            pos_reader = GeomVertexReader(vertex_data_top, "vertex")
            subobj_lvl = GlobalData["active_obj_level"]
            polys = self._subobjs["poly"]
            poly_ids = set()

            for merged_vert, indices in self._verts_to_transf[subobj_lvl].iteritems():
                pos_reader.set_row(indices[0])
                pos = Point3(pos_reader.get_data3f())
                merged_vert.set_pos(pos)
                poly_ids.update(merged_vert.get_polygon_ids())

            vert_ids = []
            polys_to_update = [polys[poly_id] for poly_id in poly_ids]

            for poly in polys_to_update:
                poly.update_center_pos()
                poly.update_normal()
                vert_ids.extend(poly.get_vertex_ids())

            merged_verts = set(self._merged_verts[vert_id] for vert_id in vert_ids)
            self.update_vertex_normals(merged_verts)

            pos_array = GeomVertexArrayData(geom_node_top.get_geom(0).get_vertex_data().get_array(0))
            normal_geoms = self._geoms["normal"]
            vertex_data = normal_geoms["pickable"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, pos_array)
            vertex_data = normal_geoms["sel_state"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, pos_array)
            model = self.get_toplevel_object()
            model.get_bbox().update(*self._origin.get_tight_bounds())

        self._origin.node().set_bounds(bounds)
        start_data.clear()
        self._pos_arrays = {"main": None, "edge": None}

    def _restore_subobj_transforms(self, old_time_id, new_time_id):

        obj_id = self.get_toplevel_object().get_id()
        prop_id = self._unique_prop_ids["subobj_transform"]

        prev_time_ids = Mgr.do("load_last_from_history", obj_id, prop_id, old_time_id)
        new_time_ids = Mgr.do("load_last_from_history", obj_id, prop_id, new_time_id)

        if prev_time_ids is None:
            prev_time_ids = ()

        if new_time_ids is None:
            new_time_ids = ()

        if not (prev_time_ids or new_time_ids):
            return

        if prev_time_ids and new_time_ids:

            i = 0

            for time_id in new_time_ids:

                if time_id not in prev_time_ids:
                    break

                i += 1

            prev_time_ids = prev_time_ids[i:]
            new_time_ids = new_time_ids[i:]

        verts = self._subobjs["vert"]
        polys = self._subobjs["poly"]

        data_id = self._unique_prop_ids["vert_pos__extra__"]

        time_ids_to_restore = {}
        prev_prop_times = {}
        positions = {}

        # to undo transformations, determine the time IDs of the transforms that
        # need to be restored by checking the data that was stored when transforms
        # occurred, at times leading up to the time that is being replaced (the old
        # time)

        for time_id in reversed(prev_time_ids):
            # time_id is a Time ID to update time_ids_to_restore with

            subobj_data = Mgr.do("load_from_history", obj_id, data_id, time_id)
            # subobj_data.get("prev", {}) yields previous transform times
            time_ids_to_restore.update(subobj_data.get("prev", {}))

        data_for_loading = {}

        # time_ids_to_restore.keys() are the IDs of vertices that need a
        # transform update
        for vert_id, time_id in time_ids_to_restore.iteritems():

            if vert_id in verts:
                prev_prop_times[vert_id] = time_id
                # since multiple vertex positions might have to be loaded from the same
                # datafile, make sure each datafile is loaded only once
                data_for_loading.setdefault(time_id, []).append(vert_id)

        for time_id, vert_ids in data_for_loading.iteritems():

            pos_data = Mgr.do("load_from_history", obj_id, data_id, time_id)["pos"]

            for vert_id in vert_ids:
                if vert_id in pos_data:
                    positions[vert_id] = pos_data[vert_id]

        # to redo transformations, retrieve the transforms that need to be restored
        # from the data that was stored when transforms occurred, at times leading
        # up to the time that is being restored (the new time)

        for time_id in new_time_ids:

            subobj_data = Mgr.do("load_from_history", obj_id, data_id, time_id)
            positions.update(subobj_data.get("pos", {}))

            for vert_id in subobj_data.get("prev", {}):
                if vert_id in verts:
                    prev_prop_times[vert_id] = time_id

        # restore the verts' previous transform time IDs
        for vert_id, time_id in prev_prop_times.iteritems():
            verts[vert_id].set_previous_property_time("transform", time_id)

        polys_to_update = set()
        vertex_data_top = self._toplvl_node.modify_geom(0).modify_vertex_data()
        pos_writer = GeomVertexWriter(vertex_data_top, "vertex")

        for vert_id, pos in positions.iteritems():
            if vert_id in verts:
                vert = verts[vert_id]
                poly = polys[vert.get_polygon_id()]
                polys_to_update.add(poly)
                vert.set_pos(pos)
                row = vert.get_row_index()
                pos_writer.set_row(row)
                pos_writer.set_data3f(pos)

        pos_array = vertex_data_top.get_array(0)

        for geom_type in ("poly", "poly_picking"):
            vertex_data = self._vertex_data[geom_type]
            vertex_data.set_array(0, pos_array)

        geoms = self._geoms

        for geom_type in ("vert", "normal"):
            vertex_data = geoms[geom_type]["pickable"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, pos_array)
            vertex_data = geoms[geom_type]["sel_state"].node().modify_geom(0).modify_vertex_data()
            vertex_data.set_array(0, pos_array)

        pos_array = GeomVertexArrayData(pos_array)
        handle = pos_array.modify_handle()
        handle.set_data(handle.get_data() * 2)
        vertex_data = geoms["edge"]["pickable"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, pos_array)
        vertex_data = geoms["edge"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data.set_array(0, pos_array)

        for poly in polys_to_update:
            poly.update_center_pos()
            poly.update_normal()

        bounds = self._origin.get_tight_bounds()

        if bounds:
            self.get_toplevel_object().get_bbox().update(*bounds)


class SelectionTransformBase(BaseObject):

    def __init__(self):

        self._obj_root = Mgr.get("object_root")
        self._center_pos = Point3()

    def update_center_pos(self):

        if not self._objs:
            return

        self._center_pos = sum([obj.get_center_pos(self.world)
                               for obj in self._objs], Point3()) / len(self._objs)

    def get_center_pos(self):

        return Point3(self._center_pos)

    def update_ui(self):

        tc_type = GlobalData["transf_center_type"]

        if tc_type == "adaptive":
            adaptive_tc_type = Mgr.get("adaptive_transf_center_type")
        else:
            adaptive_tc_type = ""

        count = len(self._objs)

        if count:
            if tc_type == "sel_center" or adaptive_tc_type:
                Mgr.do("set_transf_gizmo_pos", self.get_center_pos())

        if count == 1:
            grid_origin = Mgr.get(("grid", "origin"))
            if self._obj_level == "normal":
                h, p, r = self._objs[0].get_hpr(grid_origin)
                transform_values = {"rotate": (p, r, h)}
            else:
                x, y, z = self._objs[0].get_center_pos(grid_origin)
                transform_values = {"translate": (x, y, z)}
        else:
            transform_values = None

        Mgr.update_remotely("transform_values", transform_values)

        prev_count = GlobalData["selection_count"]

        if count != prev_count:
            Mgr.do("%s_transf_gizmo" % ("show" if count else "hide"))
            GlobalData["selection_count"] = count

        Mgr.update_remotely("selection_count")
        Mgr.update_remotely("sel_color_count")

    def set_transform_component(self, transf_type, axis, value, is_rel_value):

        obj_lvl = self._obj_level

        if obj_lvl == "normal":
            for geom_data_obj in self._groups:
                geom_data_obj.init_normal_transform()
        else:
            for geom_data_obj in self._groups:
                geom_data_obj.init_transform()

        if is_rel_value:

            if transf_type == "translate":
                transform = Vec3()
                transform["xyz".index(axis)] = value
            elif transf_type == "rotate":
                hpr = VBase3()
                hpr["zxy".index(axis)] = value
                transform = Quat()
                transform.set_hpr(hpr)
            elif transf_type == "scale":
                transform = Vec3(1., 1., 1.)
                transform["xyz".index(axis)] = max(10e-008, value)

            if obj_lvl == "normal":
                for geom_data_obj in self._groups:
                    geom_data_obj.transform_normals(transf_type, transform)
                    geom_data_obj.finalize_normal_transform()
            else:
                for geom_data_obj in self._groups:
                    geom_data_obj.transform_selection(obj_lvl, transf_type, transform)
                    geom_data_obj.finalize_transform()

        elif obj_lvl == "normal":

            # Set absolute angle for selected normals

            for geom_data_obj in self._groups:
                geom_data_obj.set_normal_sel_angle(axis, value)
                geom_data_obj.finalize_normal_transform()

            if len(self._objs) == 1:
                grid_origin = Mgr.get(("grid", "origin"))
                h, p, r = self._objs[0].get_hpr(grid_origin)
                transform_values = {"rotate": (p, r, h)}
                Mgr.update_remotely("transform_values", transform_values)

        else:

            # Set absolute coordinate for selected vertices

            for geom_data_obj in self._groups:
                geom_data_obj.set_vert_sel_coordinate(axis, value)
                geom_data_obj.finalize_transform()

            if len(self._objs) == 1:
                grid_origin = Mgr.get(("grid", "origin"))
                x, y, z = self._objs[0].get_pos(grid_origin)
                transform_values = {"translate": (x, y, z)}
                Mgr.update_remotely("transform_values", transform_values)

        if obj_lvl != "normal":

            self.update_center_pos()

            if GlobalData["transf_center_type"] in ("adaptive", "sel_center"):
                Mgr.do("set_transf_gizmo_pos", self.get_center_pos())

        self.__add_history(transf_type)

    def update_transform_values(self):

        if len(self._objs) == 1:

            subobj = self._objs[0]

            if GlobalData["coord_sys_type"] == "local":
                ref_node = subobj.get_toplevel_object().get_pivot()
            else:
                ref_node = Mgr.get(("grid", "origin"))

            if self._obj_level == "normal":
                h, p, r = subobj.get_hpr(ref_node)
                transform_values = {"rotate": (p, r, h)}
            else:
                x, y, z = subobj.get_center_pos(ref_node)
                transform_values = {"translate": (x, y, z)}

            Mgr.update_remotely("transform_values", transform_values)

    def init_transform(self):

        if self._obj_level == "normal":
            for geom_data_obj in self._groups:
                geom_data_obj.init_normal_transform()
        else:
            for geom_data_obj in self._groups:
                geom_data_obj.init_transform()

    def init_translation(self):

        self.init_transform()

    def translate(self, translation_vec):

        obj_lvl = self._obj_level

        if obj_lvl == "normal":
            for geom_data_obj in self._groups:
                geom_data_obj.transform_normals("translate", translation_vec)
        else:
            for geom_data_obj in self._groups:
                geom_data_obj.transform_selection(obj_lvl, "translate", translation_vec)

    def init_rotation(self):

        self.init_transform()

    def rotate(self, rotation):

        obj_lvl = self._obj_level

        if obj_lvl == "normal":
            for geom_data_obj in self._groups:
                geom_data_obj.transform_normals("rotate", rotation)
        else:
            for geom_data_obj in self._groups:
                geom_data_obj.transform_selection(obj_lvl, "rotate", rotation)

    def init_scaling(self):

        self.init_transform()

    def scale(self, scaling):

        obj_lvl = self._obj_level

        if obj_lvl == "normal":
            for geom_data_obj in self._groups:
                geom_data_obj.transform_normals("scale", scaling)
        else:
            for geom_data_obj in self._groups:
                geom_data_obj.transform_selection(obj_lvl, "scale", scaling)

    def finalize_transform(self, cancelled=False):

        if self._obj_level == "normal":

            for geom_data_obj in self._groups:
                geom_data_obj.finalize_normal_transform(cancelled)

            if not cancelled:
                self.update_transform_values()
                self.__add_history(GlobalData["active_transform_type"])

        else:

            for geom_data_obj in self._groups:
                geom_data_obj.finalize_transform(cancelled)

            if not cancelled:

                self.update_center_pos()

                if GlobalData["transf_center_type"] in ("adaptive", "sel_center"):
                    Mgr.do("set_transf_gizmo_pos", self.get_center_pos())
                else:
                    Mgr.do("set_transf_gizmo_pos", Mgr.get("transf_center_pos"))

                self.update_transform_values()
                self.__add_history(GlobalData["active_transform_type"])

    def __add_history(self, transf_type):

        obj_data = {}
        event_data = {"objects": obj_data}
        Mgr.do("update_history_time")

        if self._obj_level == "vert":
            subobj_descr = "vertices"
        elif self._obj_level == "edge":
            subobj_descr = "edges"
        elif self._obj_level == "poly":
            subobj_descr = "polygons"
        elif self._obj_level == "normal":
            subobj_descr = "normals"

        event_descr = '%s %s' % (transf_type.title(), subobj_descr)

        if self._obj_level == "normal":
            for geom_data_obj in self._groups:
                obj_id = geom_data_obj.get_toplevel_object().get_id()
                obj_data[obj_id] = geom_data_obj.get_data_to_store("prop_change", "normals")
        else:
            for geom_data_obj in self._groups:
                obj_id = geom_data_obj.get_toplevel_object().get_id()
                obj_data[obj_id] = geom_data_obj.get_data_to_store("prop_change", "subobj_transform")

        Mgr.do("add_history", event_descr, event_data, update_time_id=False)

    def cancel_transform(self):

        self.finalize_transform(cancelled=True)
