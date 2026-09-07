from django.conf import settings


class NoIndexMiddleware:
    """
    `settings.ROBOTS_NOINDEX` 為 True 時，在每個回應加上 `X-Robots-Tag: noindex, nofollow`。

    為什麼不只靠 robots.txt：robots.txt 擋的是「爬取」，不是「索引」——
    搜尋引擎若從別處拿到網址（例如有人把連結貼在公開頁面），仍可能把該網址列進結果，
    只是不顯示內容。`X-Robots-Tag` 是明確的「不要收錄」指令，兩者搭配才擋得乾淨。

    用 middleware 而非在 template 加 meta：header 涵蓋所有回應（含 Django Admin、
    檔案下載、JSON），不必逐一修改樣板，日後新增頁面也不會漏。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.ROBOTS_NOINDEX:
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
