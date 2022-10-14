#!/usr/bin/env python
#
# Copyright (c) CTU -- All Rights Reserved
# Created on: 2022-10-11
#     Author: Vladimir Petrik <vladimir.petrik@cvut.cz>
#

from typing import Dict, Optional
import itertools
import meshcat
from meshcat.animation import Animation
import numpy as np

from .object import Object
from .robot import Robot


class Scene:

    def __init__(self, open=True, wait_for_open=True) -> None:
        super().__init__()
        self.objects: Dict[str, Object] = {}
        self.robots: Dict[str, Robot] = {}

        self.camera_pose = np.eye(4)
        self.camera_zoom = 1.

        self.vis = meshcat.Visualizer()
        if open:
            self.vis.open()
        if wait_for_open:
            self.vis.wait()
        self.vis["/Background"].set_property("top_color", [1] * 3)
        self.vis["/Background"].set_property("bottom_color", [1] * 3)

        " Variables used internally in case we are rendering to animation "
        self._animation: Optional[Animation] = None
        self._animation_frame_counter: Optional[itertools.count] = None

    def add_object(self, obj: Object, verbose: bool = True):
        if verbose and obj.name in self.objects:
            print('Object with the same name is already inside the scene, it will be replaced. ')
        self.objects[obj.name] = obj
        self.vis[obj.name].set_object(obj.geometry, obj.material)

    def remove_object(self, obj: Object, verbose: bool = True):
        if verbose and self._animation is not None:
            print('Removing object while animating is not allowed.')
            return
        self.objects.pop(obj.name)
        self.vis[obj.name].delete()

    def add_robot(self, robot: Robot, verbose: bool = True):
        if verbose and robot.name in self.robots:
            print('Robot with the same name is already inside the scene, it will be replaced. ')
        self.robots[robot.name] = robot
        for obj in robot.objects.values():
            self.add_object(obj, verbose=verbose)

    def remove_robot(self, robot: Robot, verbose: bool = True):
        if verbose and self._animation is not None:
            print('Removing robots while animating is not allowed.')
            return
        self.robots.pop(robot.name)
        for obj in robot.objects.values():
            self.remove_object(obj, verbose=verbose)

    def render(self):
        """Render current scene either to browser, video or to the next frame of the animation. """
        if self._animation is not None:
            with self._animation.at_frame(self.vis, next(self._animation_frame_counter)) as f:
                self._update_camera(f)
                self._update_visualization_tree(f)
        else:
            self._update_camera(self.vis)
            self._update_visualization_tree(self.vis)

    def _update_camera(self, vis_tree):
        vis_tree['/Cameras/default'].set_transform(self.camera_pose)
        if self._animation is not None:
            vis_tree['/Cameras/default/rotated/<object>'].set_property("zoom", "number", self.camera_zoom)
        else:
            vis_tree['/Cameras/default/rotated/<object>'].set_property("zoom", self.camera_zoom)

    def _update_visualization_tree(self, vis_tree):
        """Update all poses of the scene in the visualization tree of the meshcat viewer"""
        for robot in self.robots.values():
            robot.fk()
        for k, o in self.objects.items():
            vis_tree[o.name].set_transform(o.pose)
        # todo: add/remove on geometry/material change?

    def animation(self, fps: int = 30):
        return AnimationContext(scene=self, fps=fps)

    @property
    def camera_pos(self):
        return self.camera_pose[:3, 3]

    @camera_pos.setter
    def camera_pos(self, p):
        self.camera_pose[:3, 3] = p

    @property
    def camera_rot(self):
        return self.camera_pose[:3, :3]

    @camera_rot.setter
    def camera_rot(self, r):
        self.camera_pose[:3, :3] = r


class AnimationContext:
    """ Used to provide 'with animation' capability for the viewer. """

    def __init__(self, scene: Scene, fps: int, name='a') -> None:
        super().__init__()
        self.scene: Scene = scene
        self.fps: int = fps
        self.name = name

    def __enter__(self):
        self.scene._animation_frame_counter = itertools.count()
        self.scene._animation = Animation(default_framerate=self.fps)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Publish animation and clear all internal changes that were required to render to frame instead of online """
        self.scene.vis[f'animations/{self.name}'].set_animation(self.scene._animation)
        self.scene._animation = None
        self.scene._animation_frame_counter = None
