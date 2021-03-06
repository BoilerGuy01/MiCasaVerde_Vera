# -*- coding: utf-8 -*-

# MIT License
#
# Copyright 2020 Kevin G. Schlosser
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be included in all copies
# or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
# FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

"""
This file is part of the **micasaverde_vera**
project https://github.com/kdschlosser/MiCasaVerde_Vera.

:platform: Unix, Windows, OSX
:license: MIT
:synopsis: scenes

.. moduleauthor:: Kevin Schlosser @kdschlosser <kevin.g.schlosser@gmail.com>
"""

import logging
import base64
import threading

# noinspection PyUnresolvedReferences
from micasaverde_vera.core.devices.scene_1 import Scene1
# noinspection PyUnresolvedReferences
from micasaverde_vera.core.devices.scene_controller_1 import SceneController1
from .event import Notify
from . import utils

logger = logging.getLogger(__name__)


class Scenes(SceneController1):

    def __init__(self, ha_gateway, node):
        self.__lock = threading.RLock()
        self.category_num = 14
        self.subcategory_num = 0
        self._scenes = []
        self.ha_gateway = ha_gateway
        self.send = ha_gateway.send

        SceneController1.__init__(self, self, node)
        SceneController1.update_node(self, node, False)

        Notify(
            self,
            'devices.{0}.created'.format(self.id)
        )

    def __iter__(self):
        with self.__lock:
            for scene in self._scenes:
                yield scene

    @utils.logit
    def get_devices(self):
        with self.__lock:
            return self.ha_gateway.devices

    @utils.logit
    def get_device(self, device):
        with self.__lock:
            return self.ha_gateway.devices[device]

    @utils.logit
    def get_room(self, room):
        with self.__lock:
            return self.ha_gateway.rooms[room]

    @utils.logit
    def get_user(self, user):
        with self.__lock:
            return self.parent.users[user]

    def __getattr__(self, item):
        with self.__lock:
            if item in self.__dict__:
                return self.__dict__[item]

            try:
                return self[item]
            except (KeyError, IndexError):
                return self._get_variable(item)[0]

    def __getitem__(self, item):
        with self.__lock:
            item = str(item)
            if item.isdigit():
                item = int(item)

            for scene in self._scenes:
                name = getattr(scene, 'name', None)
                if name is not None and name.replace(' ', '_').lower() == item:
                    return scene
                if item in (scene.name, scene.id):
                    return scene

            if isinstance(item, int):
                raise IndexError
            raise KeyError

    @utils.logit
    def update_node(self, node, full=False):
        with self.__lock:
            if node is None:
                return
            if isinstance(node, list):
                scenes = []
                for scene in node:
                    # noinspection PyShadowingBuiltins
                    id = scene['id']

                    for found_scene in self._scenes[:]:
                        if found_scene.id == id:
                            found_scene.update_node(scene, full)
                            self._scenes.remove(found_scene)
                            break
                    else:
                        found_scene = Scene(self, **scene)

                    scenes += [found_scene]

                if full:
                    for scene in self._scenes:
                        Notify(scene, scene.build_event() + '.removed')
                    del self._scenes[:]

                self._scenes += scenes

            elif isinstance(node, dict):
                SceneController1.update_node(self, node, full)


# noinspection PyPep8Naming
class Scene(Scene1):

    # noinspection PyShadowingBuiltins, PyDefaultArgument
    def __init__(
        self,
        parent,
        id,
        last_run=0,
        room=0,
        active_on_any=0,
        modeStatus=0,
        notification_only=0,
        encoded_lua=0,
        lua='',
        name='',
        users='',
        Timestamp='',
        triggers_operator='',
        triggers=[],
        timers=[],
        groups=[],
        onDashboard=False,
        paused=None,
        **kwargs
    ):
        self.__lock = threading.RLock()
        if not name:
            name = 'NO NAME ASSIGNED'

        self.parent = parent
        self.id = id
        self._room = room
        self._name = name
        self._triggers_operator = triggers_operator
        self._users = users
        self._modeStatus = modeStatus
        self._active_on_any = active_on_any
        self.Timestamp = Timestamp
        self.last_run = last_run
        self._notification_only = notification_only
        self._encoded_lua = encoded_lua
        self._lua = lua
        self._onDashboard = onDashboard
        self.paused = paused

        Notify(self, self.build_event() + '.created')
        self.groups = Groups(self, groups)
        self.triggers = Triggers(self, triggers)
        self.timers = Timers(self, timers)
        self.category_num = 9999
        self.subcategory_num = 0

        for key, value in kwargs:
            logger.info('Scene argument "{0}" has not been added. Adding it dynamically.'.format(key))
            setattr(self, key, value)

        Scene1.__init__(self, parent, {})

    def build_event(self):
        return 'scenes.{0}'.format(self.id)

    @property
    def name(self):
        with self.__lock:
            return self._name

    @name.setter
    def name(self, name):
        with self.__lock:
            self.parent.send(
                id='scene',
                action='rename',
                scene=self.id,
                name=name,
                room=self.room.id
            )

    @property
    def room(self):
        with self.__lock:
            return self.parent.ha_gateway.rooms[self._room]

    @room.setter
    def room(self, room):
        with self.__lock:
            from .rooms import Room

            if not isinstance(room, Room):
                room = self.parent.ha_gateway.rooms[room]

            self._parent.send(
                id='scene',
                action='rename',
                scene=self.id,
                name=self.name,
                room=room.id
            )

    @property
    def encoded_lua(self):
        with self.__lock:
            return self._encoded_lua

    @encoded_lua.setter
    def encoded_lua(self, encoded_lua):
        with self.__lock:
            if int(encoded_lua) and not int(self._encoded_lua):
                self._lua = base64.b64encode(self._lua)

            elif not int(encoded_lua) and int(self._encoded_lua):
                self._lua = base64.b64decode(self._lua)

            self._encoded_lua = encoded_lua

    @property
    def lua(self):
        with self.__lock:
            if int(self._encoded_lua):
                return base64.b64decode(self._lua)
            return self._lua

    @lua.setter
    def lua(self, lua):
        with self.__lock:
            if int(self._encoded_lua):
                self._lua = base64.b64encode(lua)
            else:
                self._lua = lua

    @property
    def triggers_operator(self):
        with self.__lock:
            return self._triggers_operator

    @triggers_operator.setter
    def triggers_operator(self, triggers_operator):
        with self.__lock:
            self._triggers_operator = triggers_operator

    @property
    def users(self):
        with self.__lock:
            return self._users

    @users.setter
    def users(self, users):
        with self.__lock:
            self._users = users

    @property
    def modeStatus(self):
        with self.__lock:
            return self._modeStatus

    @modeStatus.setter
    def modeStatus(self, mode_status):
        with self.__lock:
            self._modeStatus = mode_status

    @property
    def active_on_any(self):
        with self.__lock:
            return self._active_on_any

    @active_on_any.setter
    def active_on_any(self, active_on_any):
        with self.__lock:
            self._active_on_any = active_on_any

    @property
    def notification_only(self):
        with self.__lock:
            return self._notification_only

    @notification_only.setter
    def notification_only(self, notification_only):
        with self.__lock:
            self._notification_only = notification_only

    @utils.logit
    def stop_scene(self):
        with self.__lock:
            self.parent.send(
                id='action',
                serviceId=(
                    'urn:micasaverde-com:serviceId:HomeAutomationGateway1'
                ),
                action='SceneOff',
                SceneNum=self.id
            )

    @utils.logit
    def delete(self):
        with self.__lock:
            self.parent.send(
                id='scene',
                action='delete',
                scene=self.id
            )

    @property
    def onDashboard(self):
        with self.__lock:
            return bool(self._onDashboard)

    @onDashboard.setter
    def onDashboard(self, value=False):
        with self.__lock:
            self._parent.send(
                id='variableset',
                scene=self.id,
                Value=int(value),
                Variable='onDashboard',
            )

    # noinspection PyUnboundLocalVariable
    @utils.logit
    def update_node(self, node, full=False):
        with self.__lock:
            _triggers = node.pop('triggers', [])
            _groups = node.pop('groups', [])
            _timers = node.pop('timers', [])

            for key, value in node.items():
                if key == 'name':
                    old_value = self._name
                elif key == 'notification_only':
                    old_value = self._notification_only
                elif key == 'modeStatus':
                    old_value = self._modeStatus
                elif key == 'users':
                    old_value = self._users
                elif key == 'room':
                    old_value = self._room
                elif key == 'triggers_operator':
                    old_value = self._triggers_operator
                elif key == 'active_on_any':
                    old_value = self._active_on_any
                elif key == 'lua':
                    old_value = self._lua
                elif key == 'encoded_lua':
                    old_value = self._encoded_lua
                elif key == 'onDashboard':
                    old_value = self._onDashboard
                else:
                    old_value = getattr(self, key, None)

                if old_value != value:
                    if key == 'name':
                        self._name = value
                    elif key == 'notification_only':
                        self._notification_only = value
                    elif key == 'modeStatus':
                        self._modeStatus = value
                    elif key == 'users':
                        self._users = value
                    elif key == 'room':
                        self._room = value
                    elif key == 'triggers_operator':
                        self._triggers_operator = value
                    elif key == 'active_on_any':
                        self._active_on_any = value
                    elif key == 'lua':
                        self._lua = value
                    elif key == 'encoded_lua':
                        self._encoded_lua = value
                    elif key == 'onDashboard':
                        self._onDashboard = value
                    else:
                        setattr(self, key, value)

                    Notify(
                        self,
                        self.build_event() + '.{0}.changed'.format(key)
                    )

            self.triggers.update_node(_triggers, full=full)
            self.groups.update_node(_groups, full=full)
            self.timers.update_node(_timers, full=full)


class Actions(object):

    # noinspection PyDefaultArgument
    def __init__(self, parent, scene, actions=[]):
        self.__lock = threading.RLock()
        self.parent = parent
        self.scene = scene
        self.actions = list(
            Action(self, scene, **action) for action in actions
        )
        self.available_devices = AvailableDevices(self, scene)

    def build_event(self):
        return self.parent.build_event()

    def __iter__(self):
        with self.__lock:
            return iter(self.actions)

    @utils.logit
    def new_action(self):
        with self.__lock:
            self.actions += [Action(self, self.scene)]
            return self.actions[-1]

    @utils.logit
    def remove(self, action):
        with self.__lock:
            if action in self.actions:
                self.actions.remove(action)

    def __getattr__(self, item):
        with self.__lock:
            if item in self.__dict__:
                return self.__dict__[item]

            try:
                return self[item]
            except (KeyError, IndexError):
                raise AttributeError

    def __getitem__(self, item):
        with self.__lock:
            item = str(item)
            if item.isdigit():
                return self.actions[int(item)]

            for action in self.actions:
                if item == action.action:
                    return action

            raise KeyError

    @utils.logit
    def update_node(self, node, full):
        with self.__lock:
            actions = []

            while node and self.actions:
                action = node.pop(0)
                found_action = self.actions.pop(0)
                found_action.update_node(action, full)
                actions += [found_action]

            for action in node:
                actions += [Action(self, self.scene, **action)]

            if full:
                for action in self.actions:
                    Notify(action, action.build_event() + '.removed')
                del self.actions[:]

            self.actions += actions


class Action(object):
    # noinspection PyDefaultArgument
    def __init__(
        self,
        parent,
        scene,
        device=None,
        service='',
        action='',
        arguments=[],
        **kwargs
    ):
        self.__lock = threading.RLock()
        self.scene = scene
        self.parent = parent
        self.device = device
        self.service = service
        self._action = action
        Notify(self, self.build_event() + '.created')
        self.arguments = Arguments(self, arguments)

        for key, value in kwargs:
            logger.info('Action argument "{0}" has not been added. Adding it dynamically.'.format(key))
            setattr(self, key, value)

    def build_event(self):
        return self.parent.build_event() + '.actions.{0}'.format(self._action)

    @property
    def action(self):
        with self.__lock:
            if not self._action:
                return 'NO NAME ASSIGNED'
            return self._action

    @utils.logit
    def new_argument(self):
        with self.__lock:
            return self.arguments.new()

    @utils.logit
    def delete(self):
        with self.__lock:
            Notify(self, self.build_event() + '.removed')
            self.parent.remove(self)

    @utils.logit
    def update_node(self, node, full):
        with self.__lock:
            self.arguments.update_node(node.pop('arguments', []), full)

            for key, value in node.items():
                old_value = getattr(self, key, None)
                if old_value != value:
                    setattr(self, key, value)
                    Notify(
                        self,
                        self.build_event() + '.{0}.changed'.format(key)
                    )


class AvailableDevices(object):

    def __init__(self, parent, scene):
        self.parent = parent
        self.scene = scene

    def __iter__(self):
        for device in self.scene.get_devices():
            yield AvailableDevice(self.scene, device)

    def __getattr__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]

        for device in self.scene.get_devices():
            if device.name == item:
                return AvailableDevice(self.scene, device)

        raise AttributeError

    def __getitem__(self, item):
        item = str(item)
        if item.isdigit():
            item = int(item)

        for device in self.scene.get_devices():
            if item in (device.id, device.name):
                return AvailableDevice(self.scene, device)

        if isinstance(item, int):
            raise IndexError

        raise KeyError


class AvailableDevice(object):

    def __init__(self, scene, device):
        self.scene = scene
        self.name = device.name
        self.id = device.id
        self._actions = []

        for params in device.argument_mapping.values():
            arguments = []
            for key, argument in params.items():
                if key == 'orig_name':
                    continue
                arguments += [
                    dict(
                        name=argument,
                        value=None
                    )
                ]

            # noinspection PyProtectedMember
            self._actions += [
                Action(
                    parent=self,
                    scene=scene,
                    action=params['orig_name'],
                    service=device._serviceId,
                    device=device.id,
                    arguments=arguments
                )
            ]

    def __iter__(self):
        return iter(self._actions)

    def __getattr__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]

        for action in self._actions:
            if item == action.action:
                return action

        raise AttributeError('Action {0} not found.'.format(item))


class Groups(object):
    def __init__(self, scene, groups):
        self.__lock = threading.RLock()
        self.scene = scene
        self.groups = []

        for group in groups:
            self.groups += [Group(self, scene, len(self.groups) + 1, **group)]

    def build_event(self):
        return self.scene.build_event()

    def __iter__(self):
        with self.__lock:
            return iter(self.groups)

    @utils.logit
    def new_group(self):
        with self.__lock:
            self.groups += [Group(self, self.scene, len(self.groups) + 1)]
            return self.groups[-1]

    @utils.logit
    def update_node(self, node, full):
        with self.__lock:
            groups = []

            while node and self.groups:
                group = node.pop(0)
                found_group = self.groups.pop(0)
                found_group.update_node(group, full)
                groups += [found_group]

            for group in node:
                groups += [Group(self.scene, **group)]

            if full:
                for group in self.groups:
                    Notify(group, group.build_event() + '.removed')
                del self.groups[:]

            self.groups += groups

    @utils.logit
    def remove(self, group):
        with self.__lock:
            if group in self.groups:
                self.groups.remove(group)

    def __getitem__(self, item):
        with self.__lock:
            return self.groups[item]


class Group(object):

    # noinspection PyDefaultArgument, PyShadowingBuiltins
    def __init__(
            self,
            parent,
            scene,
            id,
            delay=0,
            actions=[],
            **kwargs
    ):
        self.__lock = threading.RLock()
        self.parent = parent
        self.scene = scene
        self.id = id
        self._delay = delay
        Notify(self, self.build_event() + '.created')
        self.actions = Actions(self, scene, actions)

        for key, value in kwargs:
            logger.info('Group argument "{0}" has not been added. Adding it dynamically.'.format(key))
            setattr(self, key, value)

    def build_event(self):
        return self.parent.build_event() + '.groups.{0}'.format(self.id)

    @property
    def delay(self):
        with self.__lock:
            return self._delay

    @delay.setter
    def delay(self, delay):
        with self.__lock:
            self._delay = delay

    @utils.logit
    def delete(self):
        with self.__lock:
            Notify(
                self,
                self.build_event() + '.removed'
            )
            self.scene.groups.remove(self)

    @utils.logit
    def update_node(self, node, full):
        with self.__lock:
            if self._delay != node['delay']:
                self._delay = node['delay']
                Notify(self, self.build_event() + '.delay.changed')
            self.actions.update_node(node['actions'], full)


class Triggers(object):

    def __init__(self, scene, triggers):
        self.__lock = threading.RLock()
        self.scene = scene
        self.triggers = list(
            Trigger(self, scene, **trigger) for trigger in triggers
        )

    def build_event(self):
        return self.scene.build_event()

    def __iter__(self):
        with self.__lock:
            return iter(self.triggers)

    @utils.logit
    def new_trigger(self):
        with self.__lock:
            self.triggers += [Trigger(self, self.scene, '')]
            return self.triggers[-1]

    @utils.logit
    def remove(self, trigger):
        with self.__lock:
            if trigger in self.triggers:
                self.triggers.remove(trigger)

    def __getattr__(self, item):
        with self.__lock:
            if item in self.__dict__:
                return self.__dict__[item]

            try:
                return self[item]
            except (KeyError, IndexError):
                raise AttributeError

    def __getitem__(self, item):
        with self.__lock:
            item = str(item)
            if item.isdigit():
                return self.triggers[int(item)]

            for trigger in self.triggers:
                if item == trigger.name:
                    return trigger

            raise KeyError

    @utils.logit
    def update_node(self, node, full):
        with self.__lock:
            triggers = []

            while node and self.triggers:
                trigger = node.pop(0)
                found_trigger = self.triggers.pop(0)

                found_trigger.update_node(trigger, full)
                triggers += [found_trigger]

            for trigger in node:
                triggers += [Trigger(self.scene, **trigger)]

            if full:
                for trigger in self.triggers:
                    Notify(trigger, trigger.build_event() + '.removed')
                del self.triggers[:]

            self.triggers += triggers


class Trigger(object):
    # noinspection PyDefaultArgument
    def __init__(
        self,
        parent,
        scene,
        name,
        device=None,
        template=None,
        enabled=1,
        lua='',
        encoded_lua=0,
        arguments=[],
        last_run=0,
        last_eval=0,
        users=[],
        autogen=None,
        **kwargs
    ):
        self.__lock = threading.RLock()

        if not name:
            name = 'NO NAME ASSIGNED'

        self.parent = parent
        self.scene = scene
        self._name = name
        self._device = device
        self._template = template
        self._enabled = enabled
        self._lua = lua
        self._encoded_lua = encoded_lua
        self._users = users
        self.last_run = last_run
        self.last_eval = last_eval
        self.autogen = autogen
        Notify(self, self.build_event() + '.created')
        self.arguments = Arguments(self, arguments)

        for key, value in kwargs:
            logger.info('Trigger argument "{0}" has not been added. Adding it dynamically.'.format(key))
            setattr(self, key, value)

    def build_event(self):
        return self.parent.build_event() + '.triggers.{0}'.format(self.name)

    @property
    def users(self):
        with self.__lock:
            return self._users

    @users.setter
    def users(self, value):
        with self.__lock:
            self._users = value

    @property
    def name(self):
        with self.__lock:
            if not self._name:
                return 'NO NAME ASSIGNED'

            return self._name

    @name.setter
    def name(self, name):
        with self.__lock:
            self._name = name

    @property
    def device(self):
        with self.__lock:
            return self.scene.parent.get_device(self._device)

    @device.setter
    def device(self, device):
        with self.__lock:
            device = self.scene.parent.get_device(device)
            if device is not None:
                self._device = device.id

    @property
    def template(self):
        with self.__lock:
            return self._template

    @template.setter
    def template(self, template):
        with self.__lock:
            self._template = template

    @property
    def enabled(self):
        with self.__lock:
            return self._enabled

    @enabled.setter
    def enabled(self, enabled):
        with self.__lock:
            self._enabled = enabled

    @property
    def encoded_lua(self):
        with self.__lock:
            return self._encoded_lua

    @encoded_lua.setter
    def encoded_lua(self, encoded_lua):
        with self.__lock:
            if int(encoded_lua) and not int(self._encoded_lua):
                self._lua = base64.b64encode(self._lua)

            elif not int(encoded_lua) and int(self._encoded_lua):
                self._lua = base64.b64decode(self._lua)

            self._encoded_lua = encoded_lua

    @property
    def lua(self):
        with self.__lock:
            if int(self._encoded_lua):
                return base64.b64decode(self._lua)
            return self._lua

    @lua.setter
    def lua(self, lua):
        with self.__lock:
            if int(self._encoded_lua):
                self._lua = base64.b64encode(lua)
            else:
                self._lua = lua

    @utils.logit
    def new_argument(self):
        with self.__lock:
            return self.arguments.new()

    @utils.logit
    def delete(self):
        with self.__lock:
            Notify(self, self.build_event() + '.removed')
            self.scene.triggers.remove(self)

    # noinspection PyUnboundLocalVariable
    @utils.logit
    def update_node(self, node, full=False):
        with self.__lock:
            self.arguments.update_node(node.pop('arguments', []), full)

            for key, value in node.items():
                if key == 'device':
                    old_value = self._device
                elif key == 'name':
                    old_value = self._name
                elif key == 'enabled':
                    old_value = self._enabled
                elif key == 'template':
                    old_value = self._template
                elif key == 'lua':
                    old_value = self._lua
                elif key == 'encoded_lua':
                    old_value = self._encoded_lua
                elif key == 'users':
                    old_value = self._users
                else:
                    old_value = getattr(self, key, None)

                if old_value != value:
                    if key == 'device':
                        self._device = value
                    elif key == 'name':
                        self._name = value
                    elif key == 'enabled':
                        self._enabled = value
                    elif key == 'template':
                        self._template = value
                    elif key == 'lua':
                        self._lua = value
                    elif key == 'encoded_lua':
                        self._encoded_lua = value
                    elif key == 'users':
                        self._users = value
                    else:
                        setattr(self, key, value)

                    Notify(
                        self,
                        self.build_event() + '.{0}.changed'.format(key)
                    )


class Timers(object):

    def __init__(self, scene, timers):
        self.__lock = threading.RLock()
        self.scene = scene
        self.timers = list(Timer(self, scene, **timer) for timer in timers)

    @utils.logit
    def new_timer(self, name):
        with self.__lock:
            self.timers += [Timer(self, self.scene, len(self.timers), name)]
            return self.timers[-1]

    def build_event(self):
        return self.scene.build_event()

    def __iter__(self):
        with self.__lock:
            return iter(self.timers)

    def __getattr__(self, item):
        with self.__lock:
            if item in self.__dict__:
                return self.__dict__[item]

            try:
                return self[item]
            except (KeyError, IndexError):
                raise AttributeError

    def __getitem__(self, item):
        with self.__lock:
            item = str(item)

            if item.isdigit():
                return self.timers[int(item)]

            for timer in self.timers:
                if timer.name == item:
                    return timer

            raise KeyError

    @utils.logit
    def remove(self, timer):
        with self.__lock:
            if timer in self.timers:
                self.timers.remove(timer)

    @utils.logit
    def update_node(self, node, full):
        with self.__lock:
            timers = []

            for timer in node:
                # noinspection PyShadowingBuiltins
                id = timer['id']

                for found_timer in self.timers[:]:
                    if found_timer.id == id:
                        found_timer.update_node(timer, full)
                        self.timers.remove(found_timer)
                        break
                else:
                    found_timer = Timer(self.scene, **timer)

                timers += [found_timer]

            if full:
                for timer in self.timers:
                    Notify(timer, timer.build_event() + '.removed')
                del self.timers[:]

            self.timers += timers


# noinspection PyShadowingBuiltins
class Timer(object):

    def __init__(
        self,
        parent,
        scene,
        id,
        name='',
        type='',
        enabled=1,
        days_of_week='',
        time='',
        next_run=0,
        last_run=0,
        interval=0,
        **kwargs
    ):
        self.__lock = threading.RLock()

        if not name:
            name = 'NO NAME ASSIGNED'
        self.parent = parent
        self.scene = scene
        self.id = id
        self._name = name
        self._type = type
        self._enabled = enabled
        self._days_of_week = days_of_week
        self._time = time
        self.next_run = next_run
        self.last_run = last_run
        self._interval = interval

        Notify(self, self.build_event() + '.created')

        for key, value in kwargs:
            logger.info('Timer argument "{0}" has not been added. Adding it dynamically.'.format(key))
            setattr(self, key, value)

    def build_event(self):
        return self.parent.build_event() + '.timers.{0}'.format(self.id)

    @property
    def interval(self):
        with self.__lock:
            return self._interval

    @interval.setter
    def interval(self, value=0):
        with self.__lock:
            self._interval = value

    @property
    def name(self):
        with self.__lock:
            return self._name

    @name.setter
    def name(self, name):
        with self.__lock:
            self._name = name

    @property
    def type(self):
        with self.__lock:
            return self._type

    @type.setter
    def type(self, type):
        with self.__lock:
            self._type = type

    @property
    def enabled(self):
        with self.__lock:
            return self._enabled

    @enabled.setter
    def enabled(self, enabled):
        with self.__lock:
            self._enabled = enabled

    @property
    def days_of_week(self):
        with self.__lock:
            return self._days_of_week

    @days_of_week.setter
    def days_of_week(self, days_of_week):
        with self.__lock:
            self._days_of_week = days_of_week

    @property
    def time(self):
        with self.__lock:
            return self._time

    @time.setter
    def time(self, time):
        with self.__lock:
            self._time = time

    @utils.logit
    def delete(self):
        with self.__lock:
            Notify(self, self.build_event() + '.removed')
            self.scene.timers.remove(self)

    # noinspection PyUnboundLocalVariable
    @utils.logit
    def update_node(self, node, _):
        with self.__lock:
            for key, value in node.items():
                if key == 'type':
                    old_value = self._type
                elif key == 'name':
                    old_value = self._name
                elif key == 'interval':
                    old_value = self._interval
                elif key == 'enabled':
                    old_value = self._enabled
                elif key == 'days_of_week':
                    old_value = self._days_of_week
                elif key == 'time':
                    old_value = self._time
                else:
                    old_value = getattr(self, key, None)

                if old_value != value:
                    if key == 'type':
                        self._type = value
                    elif key == 'name':
                        self._name = value
                    elif key == 'interval':
                        self._interval = value
                    elif key == 'enabled':
                        self._enabled = value
                    elif key == 'days_of_week':
                        self._days_of_week = value
                    elif key == 'time':
                        self._time = value
                    else:
                        setattr(self, key, value)

                    Notify(
                        self,
                        self.build_event() + '.{0}.changed'.format(key)
                    )


class Arguments(object):
    def __init__(self, parent, arguments):
        self.__lock = threading.RLock()
        self.parent = parent
        self.arguments = list(
            Argument(self, **argument) for argument in arguments
        )

    def build_event(self):
        return self.parent.build_event()

    @utils.logit
    def new(self):
        with self.__lock:
            if isinstance(self.parent, Action):
                self.arguments += [
                    Argument(self, name='', value=None)
                ]
            else:
                self.arguments += [
                    Argument(self, id=0, value=None)
                ]
            return self.arguments[-1]

    @utils.logit
    def update_node(self, node, full):
        with self.__lock:
            arguments = []
            for argument in node:
                for found_argument in self.arguments[:]:
                    if isinstance(self.parent, Action):
                        if found_argument.name == argument['name']:
                            found_argument.update_node(argument, full)
                            self.arguments.remove(found_argument)
                            break

                    elif found_argument.id == argument['id']:
                        found_argument.update_node(argument, full)
                        self.arguments.remove(found_argument)
                        break
                else:
                    found_argument = Argument(self, **argument)
                arguments += [found_argument]

            for argument in self.arguments:
                Notify(argument, argument.build_event() + '.removed')

            del self.arguments[:]

            self.arguments += arguments

    def __instancecheck__(self, instance):
        with self.__lock:
            return isinstance(self.parent, instance)

    def __getattr__(self, item):
        with self.__lock:
            if item in self.__dict__:
                return self.__dict__[item]

            try:
                return self[item]
            except (KeyError, IndexError):
                raise AttributeError

    def __getitem__(self, item):
        with self.__lock:
            item = str(item)
            if item.isdigit():
                for argument in self.arguments:
                    if argument.id == int(item):
                        return argument
                raise IndexError

            for argument in self.arguments:
                if argument.name == item:
                    return argument

            raise KeyError

    @utils.logit
    def remove(self, argument):
        with self.__lock:
            if argument in self.arguments:
                self.arguments.remove(argument)


# noinspection PyShadowingBuiltins, PyUnresolvedReferences
class Argument(object):

    def __init__(self, parent, value, name=None, id=None):
        self.__lock = threading.RLock()
        self.parent = parent
        if isinstance(self.parent.parent, Action):
            if not name:
                name = 'NO NAME ASSIGNED'
            self.name = name
        else:
            if id is None:
                id = 'NO ID ASSIGNED'
            self.id = id

        self._value = value
        Notify(self, self.build_event() + '.created')

    def build_event(self):
        if isinstance(self.parent.parent, Action):
            event = self.name
        else:
            event = self.id
        return self.parent.build_event() + '.arguments.{0}'.format(event)

    @utils.logit
    def update_node(self, node, _):
        with self.__lock:
            for key, value in node.items():
                if key == 'value':
                    old_value = self._value
                else:
                    old_value = getattr(self, key, None)

                if old_value != value:
                    Notify(
                        self,
                        self.build_event() + '.{0}.changed'.format(key)
                    )

                if key == 'value':
                    self._value = value
                else:
                    setattr(self, key, value)

    @property
    def value(self):
        with self.__lock:
            return self._value

    @value.setter
    def value(self, value):
        with self.__lock:
            self._value = value

    @utils.logit
    def delete(self):
        with self.__lock:
            Notify(self, self.build_event() + '.removed')
            self.parent.remove(self)
