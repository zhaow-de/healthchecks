from collections.abc import Callable

from django.http import HttpResponse

type JSONDict = dict[str, JSONValue]
type JSONList = list[JSONValue]
type JSONValue = JSONDict | JSONList | str | int | float | bool | None


type ViewFunc = Callable[..., HttpResponse]
