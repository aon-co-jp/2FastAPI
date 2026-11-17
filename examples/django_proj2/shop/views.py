from django.shortcuts import render


def hello(request):
    name = request.GET.get("name", "world")
    return render(request, "shop/hello.html", {"name": name, "items": [1, 2, 3]})


def notfound(request):
    return render(request, "shop/hello.html", {"name": "x", "items": []}, status=404)
