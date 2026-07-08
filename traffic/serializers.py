from rest_framework import serializers
from .models import Route, UserDevice, SavedRoute, DeviceToken
from .models import RouteAlternative, TrafficAlert

class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ['id', 'start', 'destination', 'travel_time', 'created_at']
        read_only_fields = ['id', 'created_at']

class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = ['id', 'token', 'device', 'created_at']
        read_only_fields = ['id', 'created_at']

# Serializer for SavedRoute (API)
class SavedRouteSerializer(serializers.ModelSerializer):
    alternatives = serializers.ListSerializer(child=serializers.DictField(), required=False)

    class Meta:
        model = SavedRoute
        fields = [
            'route_id', 'user', 'origin', 'destination', 'distance_km', 'duration_text',
            'polyline', 'leaving_time', 'alert_time', 'primary_route', 'selected_routes',
            'created_at', 'last_checked', 'last_checked_duration', 'alert_enabled', 'alternatives'
        ]
        read_only_fields = ['route_id', 'created_at', 'last_checked']

    def create(self, validated_data):
        import datetime
        alts = validated_data.pop('alternatives', [])
        # normalize time fields if strings
        lt = validated_data.get('leaving_time')
        at = validated_data.get('alert_time')
        def _parse_time(v):
            if v is None:
                return None
            if isinstance(v, str):
                try:
                    # try ISO / HH:MM[:SS]
                    return datetime.time.fromisoformat(v)
                except Exception:
                    try:
                        return datetime.datetime.strptime(v, '%H:%M').time()
                    except Exception:
                        return None
            return v

        if lt is not None:
            validated_data['leaving_time'] = _parse_time(lt)
        if at is not None:
            validated_data['alert_time'] = _parse_time(at)

        route = SavedRoute.objects.create(**validated_data)
        for a in alts:
            RouteAlternative.objects.create(saved_route=route, **a)
        return route

    def update(self, instance, validated_data):
        import datetime
        alts = validated_data.pop('alternatives', None)
        def _parse_time(v):
            if v is None:
                return None
            if isinstance(v, str):
                try:
                    return datetime.time.fromisoformat(v)
                except Exception:
                    try:
                        return datetime.datetime.strptime(v, '%H:%M').time()
                    except Exception:
                        return None
            return v

        if 'leaving_time' in validated_data:
            validated_data['leaving_time'] = _parse_time(validated_data.get('leaving_time'))
        if 'alert_time' in validated_data:
            validated_data['alert_time'] = _parse_time(validated_data.get('alert_time'))

        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if alts is not None:
            # simple approach: delete existing alternatives and recreate
            instance.alternatives.all().delete()
            for a in alts:
                RouteAlternative.objects.create(saved_route=instance, **a)
        return instance


class SyncRouteSerializer(serializers.ModelSerializer):
    # map Flutter field names to model fields
    distance = serializers.FloatField(source='distance_km', required=False, allow_null=True)
    duration = serializers.CharField(source='duration_text', required=False, allow_blank=True)
    selected_routes = serializers.JSONField(required=False, allow_null=True)
    primary_route = serializers.JSONField(required=False, allow_null=True)
    polyline = serializers.CharField(required=False, allow_blank=True)
    leaving_time = serializers.CharField(required=False, allow_blank=True)
    alert_time = serializers.CharField(required=False, allow_blank=True)
    alert_enabled = serializers.BooleanField(required=False)

    class Meta:
        model = SavedRoute
        # don't include 'user' in writable fields; user comes from request
        fields = [
            'route_id', 'origin', 'destination', 'distance', 'duration', 'selected_routes',
            'primary_route', 'polyline', 'leaving_time', 'alert_time', 'alert_enabled', 'created_at'
        ]
        read_only_fields = ['route_id', 'created_at']

    def validate(self, data):
        # ensure origin/destination exist
        origin = data.get('origin') or data.get('origin')
        destination = data.get('destination') or data.get('destination')
        if not origin or not destination:
            raise serializers.ValidationError('origin and destination are required')
        return data

    def _parse_time(self, value):
        # accepts 'HH:MM' or ISO time strings
        import datetime
        if value is None or value == '':
            return None
        if isinstance(value, datetime.time):
            return value
        try:
            return datetime.time.fromisoformat(value)
        except Exception:
            try:
                return datetime.datetime.strptime(value, '%H:%M').time()
            except Exception:
                return None

    def create(self, validated_data):
        # validated_data keys use model field names for mapped fields
        # move selected_routes & primary_route from root if present
        selected = validated_data.pop('selected_routes', None)
        primary = validated_data.pop('primary_route', None)

        # handle leaving_time/alert_time which may be strings mapped to keys
        lt = validated_data.pop('leaving_time', None)
        at = validated_data.pop('alert_time', None)
        if lt is not None:
            validated_data['leaving_time'] = self._parse_time(lt)
        if at is not None:
            validated_data['alert_time'] = self._parse_time(at)

        # ensure distance_km and duration_text exist if provided
        # user must be provided by view when calling serializer.save(user=request.user)
        route = SavedRoute.objects.create(**validated_data)
        if selected is not None:
            route.selected_routes = selected
        if primary is not None:
            route.primary_route = primary
        route.save()
        return route

class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['username', 'token', 'created_at']
        read_only_fields = ['created_at']


class TrafficAlertSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = TrafficAlert
        fields = ['id', 'severity', 'description', 'origin', 'destination', 'timestamp']
        read_only_fields = ['id', 'timestamp']