from rest_framework import status, viewsets
from rest_framework.response import Response

ITEMS = {1: {"id": 1, "name": "one"}, 2: {"id": 2, "name": "two"}}


class ItemViewSet(viewsets.ViewSet):
    def list(self, request):
        limit = int(request.query_params.get("limit", 10))
        return Response(list(ITEMS.values())[:limit])

    def create(self, request):
        name = request.data.get("name")
        if not name:
            return Response({"error": "name required"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": 3, "name": name}, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        item = ITEMS.get(int(pk))
        if item is None:
            return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(item)

    def update(self, request, pk=None):
        return Response({"id": int(pk), "name": request.data.get("name", "")})

    def destroy(self, request, pk=None):
        return Response(status=status.HTTP_204_NO_CONTENT)
