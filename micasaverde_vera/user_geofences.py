# -*- coding: utf-8 -*-
#
# This file is part of EventGhost.
# Copyright © 2005-2016 EventGhost Project <http://www.eventghost.net/>
#
# EventGhost is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# EventGhost is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with EventGhost. If not, see <http://www.gnu.org/licenses/>.


from event import EventHandler


class UserGeofences(object):


    def __init__(self, parent, node):
        self._parent = parent
        self.send = parent.send
        self._geofences = []
        self._bindings = []

        if node is not None:
            for geofence in node:
                self._geofences += [UserGeoFence(self, geofence)]

    def get_geofences(self, number):

        res = []
        for geofence in self._geofences:
            if number in (geofence.iduser, geofence.name):
                res += [geofence]
        return res

    def get_user(self, number):
        return self._parent.get_user(number)

    def register_event(self, callback, attribute=None):
        self._bindings += [EventHandler(self, callback, None)]
        return self._bindings[-1]

    def unregister_event(self, event_handler):
        if event_handler in self._bindings:
            self._bindings.remove(event_handler)

    def update_node(self, node, full=False):
        if node is not None:
            geofences = []

            for geofence in node:
                iduser = geofence['iduser']
                for found_geofence in self._geofences[:]:
                    if found_geofence.iduser == iduser:
                        found_geofence.update_node(geofence, full)
                        self._geofences.remove(found_geofence)
                        break
                else:
                    found_geofence = UserGeoFence(self, geofence)

                    for event_handler in self._bindings:
                        event_handler('new', geofence=found_geofence)

                geofences += [found_geofence]
            if full:
                for geofence in self._geofences:

                    for event_handler in self._bindings:
                        event_handler('remove', geofence=geofence)
                del self._geofences[:]

            self._geofences += geofences


class GeoTag(object):
    def __init__(self, parent, node):
        self._parent = parent
        self._bindings = []

        def get(attr):
            return node.pop(attr, None)

        self._PK_User = get('PK_User')
        self.id = get('id')
        self.accuracy = get('accuracy')
        self.ishome = get('ishome')
        self.notify = get('notify')
        self.radius = get('radius')
        self.address = get('address')
        self.color = get('color')
        self.latitude = get('latitude')
        self.longitude = get('longitude')
        self.name = get('name')
        self.status = get('status')

        for key, value in node.items():
            self.__dict__[key] = value

    @property
    def PK_User(self):
        return self._parent.get_user(self._PK_User)


    def register_event(self, callback, attribute=None):
        self._bindings += [EventHandler(self, callback, attribute)]
        return self._bindings[-1]

    def unregister_event(self, event_handler):
        if event_handler in self._bindings:
            self._bindings.remove(event_handler)

    def update_node(self, node):

        for key, value in node.items():

            if key == 'PK_User':
                old_value = self._PK_User
            else:
                old_value = getattr(self, key, None)

            if old_value is None:
                event_handler(
                    'new',
                    geofence=self._parent,
                    geotag=self,
                    attribute=key,
                    value=value
                )

                setattr(self, key, value)

            elif old_value != value:
                event_handler(
                    'changed',
                    geofence=self._parent,
                    geotag=self,
                    attribute=key,
                    value=value
                )
                if key == 'PK_User':
                    self._PK_User = value
                else:
                    setattr(self, key, value)


class UserGeoFence(object):

    def __init__(self, parent, node):
        self._parent = parent
        self._bindings = []

        self._geotags = []
        self.iduser = node.pop('iduser', None)

        for geotag in node.pop('geotags', []):
            self._geotags += [GeoTag(self, geotag)]

    def __iter__(self):
        for geotag in self._geotags:
            yield geotag

    def register_event(self, callback, attribute=None):
        self._bindings += [EventHandler(self, callback, None)]
        return self._bindings[-1]

    def unregister_event(self, event_handler):
        if event_handler in self._bindings:
            self._bindings.remove(event_handler)

    @property
    def user(self):
        return self.get_user(self.iduser)

    def get_user(self, number):
        return self._parent.get_user(number)

    def update_node(self, node, full):
        geotags = []

        for geotag in node.pop('geotags', []):
            id = geotag['id']

            for found_geotag in self._geotags[:]:
                if found_geotag.id == id:
                    found_geotag.update_node(geotag)
                    self._geotags.remove(found_geotag)
                    break
            else:
                found_geotag = GeoTag(self, geotag)

                for event_handler in self._bindings:
                    event_handler(
                        'new',
                        geofence=self,
                        geotag=geotag
                    )

            geotags += [found_geotag]

        if full:
            for geotag in self._geotags:

                for event_handler in self._bindings:
                    event_handler(
                        'remove',
                        geofence=self,
                        geotag=geotag
                    )
            del self._geotags[:]

        self._geotags += geotags
