from django.shortcuts import render


def index(request):
    return render(request, 'public/index.html')


def about(request):
    return render(request, 'public/about.html')


def rules(request):
    return render(request, 'public/rules.html')
