from pathlib import Path

src = Path('archive/2026-09-12-monday.html')
out = Path('archive/2026-09-12-monday-styled.html')
html = src.read_text(encoding='utf-8')
style = r'''
<style>
  html,body{background:#f8f7f0!important;color:#173b3a!important}
  body{max-width:none!important;margin:0!important;padding:20px 10px 40px!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Helvetica,Arial,sans-serif!important;line-height:1.6!important}
  body:before{content:"PULMORADAR\A 肺部基础研究周报\A Weekly Digest of Pulmonary Basic Research";white-space:pre;display:block;max-width:680px;margin:0 auto 0;padding:28px 32px 24px;background:#f8f7f0;color:#173b3a;font-size:30px;font-weight:700;line-height:1.45;box-sizing:border-box;border-top:9px solid #087c78;border-left:1px solid #e1e9e6;border-right:1px solid #e1e9e6}
  body>h1,body>p:first-of-type,body>p:nth-of-type(2),body>ul:first-of-type{max-width:680px;margin-left:auto!important;margin-right:auto!important;padding-left:32px;padding-right:32px;box-sizing:border-box}
  body>h1{margin-top:0!important;background:#f8f7f0;color:#087c78!important;font-size:13px!important;letter-spacing:.16em;text-transform:uppercase;border-left:1px solid #e1e9e6;border-right:1px solid #e1e9e6;height:0;overflow:hidden}
  body>p:first-of-type{margin-top:0!important;padding-top:0;background:#f8f7f0;color:#315452!important;border-bottom:2px solid #087c78;padding-bottom:18px;border-left:1px solid #e1e9e6;border-right:1px solid #e1e9e6}
  body>p:nth-of-type(2),body>ul:first-of-type{background:#fff;padding-top:18px;padding-bottom:18px;border-left:1px solid #e1e9e6;border-right:1px solid #e1e9e6;color:#667575!important;font-size:13px!important}
  body>h2{max-width:680px;margin:24px auto 16px!important;padding:13px 18px;background:#087c78;color:#fff!important;font-size:20px!important;box-sizing:border-box}
  body>article{max-width:680px;margin-left:auto!important;margin-right:auto!important;padding:0 24px 24px!important;background:#fff;border:1px solid #d9e5e2;border-radius:12px;box-sizing:border-box;box-shadow:0 2px 8px rgba(18,73,70,.05)}
  body>article:before{content:"";display:block;height:6px;background:#087c78;margin:0 -24px 20px}
  body>article h3{color:#173b3a!important;font-size:20px!important;line-height:1.35!important}
  body>article p,body>article li{color:#405251!important;font-size:14px!important;line-height:1.8!important}
  body>article p strong{color:#087c78!important}
  body>article a{color:#087c78!important;font-weight:700}
  body>article ul{padding-left:22px}
  @media(max-width:600px){body{padding:0!important}body:before{padding:24px 18px 20px;font-size:25px}body>h1,body>p:first-of-type,body>p:nth-of-type(2),body>ul:first-of-type{padding-left:18px;padding-right:18px}body>article{padding-left:18px!important;padding-right:18px!important;border-radius:0}body>article:before{margin-left:-18px;margin-right:-18px}}
</style>
'''
html = html.replace('</head>', style + '</head>')
out.write_text(html, encoding='utf-8')
print(out)
