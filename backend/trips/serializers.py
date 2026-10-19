from rest_framework import serializers


class TripAskSerializer(serializers.Serializer):
    """checks that the stuff the user sent us makes sense before we do anything"""

    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure_iso = serializers.DateTimeField()
    load_lbs = serializers.FloatField(min_value=0, max_value=200_000)
    sample_miles = serializers.ChoiceField(choices=[10, 25, 50], default=25)

    def validate(self, attrs):
        if attrs["origin"].strip().lower() == attrs["destination"].strip().lower():
            raise serializers.ValidationError("Origin and destination are the same place, silly.")
        return attrs
