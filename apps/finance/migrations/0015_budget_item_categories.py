"""收支分類補上試算表「收支」分頁的預算項目，並把舊的匯入紀錄歸回正確分類。

背景：試算表的預算項目（團練室、指揮費用、宣傳、錄音錄影…）比系統內建分類細，
匯入時只能把對不上的塞進「其他」或粗略併入「場地費」「師資費」，導致收支明細的分類
跟試算表的項目對不上。這裡新增缺少的分類（場地費、樂譜費原本就有，不重複建）。

- 分類以「名稱」判斷是否已存在：幹部若已在後台自己建過同名分類，就沿用、不重複建
  （名稱有唯一限制），其代碼由那筆分類自己決定。
- 舊紀錄歸回：只動「類型為支出、分類還停在舊對照結果、描述以項目名稱開頭」的紀錄
  （匯入程式寫的描述是「項目：說明」，見 import_sheet._import_expenses），
  幹部手動建的、描述不是這個格式的紀錄不碰。
- 回退（reverse）不做事：新增的分類與歸類留著無害，要移除請在後台處理。
"""

from django.db import migrations

# (預算項目, 分類名稱, 排序, 舊匯入程式放的分類代碼)
# 場地費、樂譜費原本就是內建分類，舊紀錄本來就歸對了，所以不在這張表裡。
BUDGET_CATEGORIES = [
    ('團練室', '團練室', 110, ('venue',)),
    ('指揮費用', '指揮費用', 120, ('instructor',)),
    ('架站與伺服器費', '架站與伺服器費', 130, ('other',)),
    ('開發網站', '架站與伺服器費', 130, ('other',)),     # 舊名
    ('宣傳', '宣傳', 140, ('other',)),
    ('音樂會錄音錄影', '音樂會錄音錄影', 150, ('other',)),
    ('工作人員', '工作人員', 160, ('other',)),
    ('創團行政費', '創團行政費', 170, ('other',)),
    ('大型樂器', '大型樂器', 180, ('other',)),
]

# 新建分類用的固定代碼（紀錄以代碼指向分類）
CODES = {
    '團練室': 'practice_room',
    '指揮費用': 'conductor_fee',
    '架站與伺服器費': 'hosting',
    '宣傳': 'promotion',
    '音樂會錄音錄影': 'recording',
    '工作人員': 'staff',
    '創團行政費': 'founding_admin',
    '大型樂器': 'large_instrument',
}


def add_budget_categories(apps, schema_editor):
    FinanceCategory = apps.get_model('finance', 'FinanceCategory')
    FinanceRecord = apps.get_model('finance', 'FinanceRecord')

    for _, name, order, _ in BUDGET_CATEGORIES:
        if not FinanceCategory.objects.filter(name=name).exists():
            FinanceCategory.objects.create(
                code=CODES[name], name=name, kind='expense', sort_order=order,
            )

    for item, name, _, old_codes in BUDGET_CATEGORIES:
        category = FinanceCategory.objects.get(name=name)
        candidates = FinanceRecord.objects.filter(type='expense', category_id__in=old_codes)
        for pattern in ({'description': item},
                        {'description__startswith': f'{item}：'},
                        {'description__startswith': f'{item}（'}):
            candidates.filter(**pattern).update(category_id=category.code)


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0014_rename_huifei_to_tuanfei'),
    ]

    operations = [
        migrations.RunPython(add_budget_categories, migrations.RunPython.noop),
    ]
