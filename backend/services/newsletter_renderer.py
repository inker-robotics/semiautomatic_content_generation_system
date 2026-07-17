from core.schemas import NewsletterPayload, NewsletterEdition


def _render_edition_html(edition: NewsletterEdition, accent: str, label: str, is_student: bool) -> str:
    sections_html = ""
    for section in edition.sections:
        section_dict = section.model_dump() if hasattr(section, "model_dump") else section
        img_url = section_dict.get("image_url", "")
        
        # Massive image with cover fit
        if img_url:
            img_html = f'''
            <img src="{img_url}" style="width: 100%; height: auto; max-height: 500px; object-fit: cover; border-radius: 16px; margin-bottom: 24px; border: 3px solid {accent};" alt="Tech Image" />
            '''
        else:
            img_html = ""
        
        # Massive typography for WhatsApp readability
        section_block = f"""
        <div style="margin-bottom: 32px; padding: 24px; background: {('#0f172a' if is_student else '#f8fafc')}; border-left: 6px solid {accent}; border-radius: 0 20px 20px 0; box-shadow: 0 8px 24px rgba(0,0,0,{('0.5' if is_student else '0.1')});">
            {img_html}
            <h3 style="margin: 0 0 16px; color: {accent}; font-size: 48px; font-weight: 900; letter-spacing: -0.02em; text-transform: uppercase; line-height: 1.1;">{section_dict.get('title', '')}</h3>
            <p style="margin: 0 0 20px; color: {('#e2e8f0' if is_student else '#1e293b')}; line-height: 1.5; font-size: 36px; font-weight: 500;">{section_dict.get('body', '')}</p>
            <div style="font-size: 28px; color: {('#94a3b8' if is_student else '#64748b')}; background: {('#020617' if is_student else '#f1f5f9')}; padding: 16px; border-radius: 12px; border: 2px solid {accent}30;">
                <span style="display: block; margin-bottom: 8px; color: {accent}; font-weight: 700;">📡 <strong>Source:</strong> <a href="{section_dict.get('source_url', '#')}" target="_blank" style="color: {accent}; text-decoration: underline;">{section_dict.get('source', '')}</a></span>

            </div>
        </div>
        """
        
        sections_html += section_block

    # Theme-specific header styling
    if is_student:
        header_bg = "#0f172a"
        header_text_color = "#f8fafc"
        header_border = f"4px solid {accent}"
        label_bg = accent
        label_text = "#0f172a"
    else:
        header_bg = "#ffffff"
        header_text_color = "#0f172a"
        header_border = f"3px solid {accent}"
        label_bg = accent
        label_text = "#ffffff"
    
    return f"""
    <div style="margin-bottom: 48px;">
        <div style="text-align: center; margin-bottom: 28px;">
            <span style="background: {label_bg}; color: {label_text}; font-weight: 900; font-size: 32px; padding: 12px 36px; border-radius: 32px; text-transform: uppercase; letter-spacing: 0.2em; display: inline-block; box-shadow: 0 6px 20px {accent}60;">{label}</span>
        </div>
        <div style="background: {header_bg}; border: {header_border}; border-radius: 24px; overflow: hidden; box-shadow: 0 12px 48px rgba(0,0,0,{('0.7' if is_student else '0.15')});">
            <div style="padding: 40px;">
                <h2 style="margin: 0 0 16px; color: {header_text_color}; font-size: 64px; font-weight: 900; letter-spacing: -0.03em; line-height: 1.1;">{edition.subject_line}</h2>
                <p style="margin: 0 0 28px; color: {('#94a3b8' if is_student else '#64748b')}; font-size: 36px; font-style: italic; line-height: 1.3;">{edition.preheader}</p>
                <p style="margin: 0 0 36px; color: {header_text_color}; font-size: 38px; line-height: 1.5; font-weight: 500;">{edition.intro}</p>
                
                {sections_html}
                
                <div style="margin-top: 24px; padding-top: 28px; border-top: 3px solid {accent}40;">
                    <p style="margin: 0 0 16px; color: {header_text_color}; font-size: 34px; line-height: 1.5;">{edition.closing}</p>
                    <p style="margin: 0; color: {accent}; font-weight: 900; font-size: 38px; text-transform: uppercase; letter-spacing: 0.08em;">🚀 {edition.call_to_action}</p>
                </div>
            </div>
        </div>
    </div>
    """


def render_single_edition_poster(edition: dict, accent: str, title: str, is_student: bool, client_logo_url: str | None = None) -> str:
    """Render a single edition as an edge-to-edge mobile poster with a fixed grid layout so it doesn't overflow length-wise."""
    # Theme-specific header
    if is_student:
        header_bg = "rgba(15, 23, 42, 0.85)"
        header_text_color = "#f8fafc"
        header_border = f"1px solid rgba(255,255,255,0.1)"
        label_bg = accent
        label_text = "#020617"
        bg_css = f"background-color: #020617; background-image: radial-gradient(circle at 15% 50%, {accent}20, transparent 35%), radial-gradient(circle at 85% 30%, #8b5cf620, transparent 35%);"
    else:
        header_bg = "rgba(255, 255, 255, 0.95)"
        header_text_color = "#0f172a"
        header_border = f"1px solid rgba(0,0,0,0.05)"
        label_bg = accent
        label_text = "#ffffff"
        bg_css = f"background-color: #f1f5f9; background-image: radial-gradient(circle at 15% 50%, {accent}15, transparent 35%), radial-gradient(circle at 85% 30%, #f59e0b15, transparent 35%);"

    sections_html = ""
    for section in edition.get("sections", []):
        img_url = section.get("image_url", "")
        
        # News Card with Image and Text Description
        if img_url:
            img_html = f'''
            <div style="position: relative; border-radius: 24px; overflow: hidden; display: flex; flex-direction: column; background: {header_bg}; box-shadow: 0 20px 40px rgba(0,0,0,{('0.6' if is_student else '0.1')}); border: 2px solid {accent}40; margin-bottom: 30px;">
                <img src="{img_url}" style="width: 100%; height: 480px; display: block; object-fit: cover;" alt="Tech Image" />
                <div style="padding: 36px;">
                    <h2 style="margin: 0 0 16px; font-family: 'Outfit', sans-serif; font-size: 42px; font-weight: 800; color: {header_text_color}; line-height: 1.2;">{section.get('title', '')}</h2>
                    <p style="margin: 0; font-family: 'Inter', sans-serif; font-size: 32px; color: {('#cbd5e1' if is_student else '#475569')}; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;">{section.get('body', '')}</p>
                </div>
            </div>
            '''
        else:
            img_html = ""
            
        sections_html += img_html
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">
        <style>
            .poster-container {{
                width: 1080px; 
                height: 1920px; 
                {bg_css}
                font-family: 'Inter', sans-serif;
                box-sizing: border-box;
                padding: 48px;
                display: flex;
                flex-direction: column;
            }}
            .flex-layout {{
                display: flex;
                flex-direction: column;
                gap: 36px;
                flex-grow: 1;
                margin-top: 36px;
                margin-bottom: 24px;
            }}
            .inker-logo {{
                display: flex;
                align-items: center;
                gap: 20px;
                margin-bottom: 40px;
            }}
            .brand-logo-box {{
                width: 64px;
                height: 64px;
                background: linear-gradient(135deg, {accent}, #8b5cf6);
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-family: 'Outfit', sans-serif;
                font-weight: 900;
                font-size: 28px;
                letter-spacing: -1px;
                box-shadow: 0 8px 20px {accent}40;
            }}
            .brand-text-box {{
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}
            .brand-text-1 {{
                font-family: 'Outfit', sans-serif;
                color: {header_text_color};
                font-size: 32px;
                font-weight: 900;
                line-height: 1;
                letter-spacing: 2px;
                text-transform: uppercase;
            }}
            .brand-text-2 {{
                color: {accent};
                font-size: 18px;
                font-weight: 700;
                letter-spacing: 4px;
                text-transform: uppercase;
                margin-top: 4px;
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0;">
        <div class="poster-container">
            <!-- Authentic Branding -->
            {f'''
            <div class="inker-logo">
                <img src="{client_logo_url}" style="height: 80px; max-width: 300px; border-radius: 8px; object-fit: contain;" />
            </div>
            ''' if client_logo_url else f'''
            <div class="inker-logo">
                <div class="brand-logo-box">IR</div>
                <div class="brand-text-box">
                    <span class="brand-text-1">INKER ROBOTICS</span>
                    <span class="brand-text-2">Tech Brief</span>
                </div>
            </div>
            '''}
            
            <!-- Header section -->
            <div style="background: {header_bg}; border: {header_border}; border-radius: 24px; padding: 40px; box-shadow: 0 16px 40px rgba(0,0,0,{('0.4' if is_student else '0.05')}); flex-shrink: 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <span style="background: {label_bg}; color: {label_text}; font-weight: 900; font-size: 24px; padding: 10px 28px; border-radius: 32px; text-transform: uppercase; letter-spacing: 0.15em; font-family: 'Outfit', sans-serif;">{title}</span>
                </div>
                <h1 style="margin: 0 0 16px; color: {header_text_color}; font-family: 'Outfit', sans-serif; font-size: 56px; font-weight: 900; letter-spacing: -0.02em; line-height: 1.15; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis;">{edition.get('subject_line', '')}</h1>
                <p style="margin: 0; color: {accent}; font-size: 32px; font-weight: 500; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis;">{edition.get('preheader', '')}</p>
            </div>
            
            <!-- Cards Flex Stack -->
            <div class="flex-layout">
                {sections_html}
            </div>
        </div>
    </body>
    </html>
    """


def render_dual_newsletter_email_html(payload: dict, edition_title: str, edit_url: str, approve_url: str, share_url: str) -> str:
    try:
        data = NewsletterPayload(**payload.get("editions", payload))
        editions = data.model_dump()
        
        for aud_name, edition in editions.items():
            for i, sec in enumerate(edition["sections"]):
                sec["image_url"] = payload["editions"][aud_name]["sections"][i].get("image_url", "")
            
    except Exception as e:
        return f"<p style='color: red;'>Error parsing payload: {e}</p>"

    editions_html = ""
    theme_colors = ["#06b6d4", "#f59e0b", "#10b981", "#8b5cf6", "#ec4899"]
    idx = 0
    
    # We must pass actual NewsletterEdition dict back to _render_edition_html, but with image_urls populated
    # The image urls are added to payload by engine.py, so we pull them from payload.
    for aud_name, edition in payload.get("editions", {}).items():
        accent = theme_colors[idx % len(theme_colors)]
        is_student_theme = (idx % 2 == 0)
        title_display = f"✨ {aud_name.capitalize()} Edition"
        editions_html += _render_edition_html(NewsletterEdition(**edition), accent, title_display, is_student_theme)
        idx += 1

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; width: 100%; background: #020617; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <div style="width: 100%; padding: 40px; box-sizing: border-box;">
            
            <div style="text-align: right; margin-bottom: 28px;">
                <a href="{share_url}" target="_blank" style="color: #cbd5e1; text-decoration: none; font-size: 12px; border: 1px solid #334155; padding: 8px 16px; border-radius: 6px; background: #0f172a; font-weight: 600;">🔗 Read Online or Share</a>
            </div>

            {editions_html}

            <div style="background: #0f172a; border-radius: 12px; padding: 28px; text-align: center; margin-top: 40px; border: 1px dashed #334155;">
                <h4 style="margin: 0 0 18px; color: #f8fafc; font-size: 16px; font-weight: 700;">Manager Review Required</h4>
                <a href="{approve_url}" style="display: inline-block; background: #10b981; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; margin: 0 8px 12px; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);">✅ Approve & Publish</a>
                <a href="{edit_url}" style="display: inline-block; background: #3b82f6; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; margin: 0 8px 12px; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);">✏️ Request Edits</a>
            </div>
            
        </div>
    </body>
    </html>
    """