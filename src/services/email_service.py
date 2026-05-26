import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("EmailService")

class EmailService:
    """
    Renders a premium glassmorphic HTML email template and dispatches 
    it via SMTP.
    """
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.sender_email = os.getenv("SENDER_EMAIL")

    def _render_html_template(self, email: str, report_data: Dict[str, Any], total_value: float) -> str:
        """
        Renders the beautiful glassmorphic dark-theme HTML email template.
        """
        health_score = report_data.get("health_score", 0)
        risk_score = report_data.get("risk_score", 0.0)
        summary = report_data.get("executive_summary", "No summary available.")
        
        # Color palettes based on scores
        health_color = "#10B981" if health_score >= 70 else ("#F59E0B" if health_score >= 40 else "#EF4444")
        risk_color = "#EF4444" if risk_score >= 7.0 else ("#F59E0B" if risk_score >= 4.0 else "#10B981")
        
        # Generate actionable insights list
        insights_html = ""
        insights = report_data.get("insights", [])
        if not insights:
            insights_html = "<p style='color: #a0aec0;'>Your portfolio news is stable. No major alerts today.</p>"
        else:
            for item in insights:
                bg_color = "rgba(16, 185, 129, 0.08)"
                border_color = "#10B981"
                emoji = "🟢"
                
                itype = item.get("type", "info").lower()
                if itype == "warning":
                    bg_color = "rgba(239, 68, 68, 0.08)"
                    border_color = "#EF4444"
                    emoji = "⚠️"
                elif itype == "info":
                    bg_color = "rgba(59, 130, 246, 0.08)"
                    border_color = "#3B82F6"
                    emoji = "ℹ️"
                
                insights_html += f"""
                <div style="background: {bg_color}; border-left: 4px solid {border_color}; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
                    <div style="font-weight: bold; color: #ffffff; margin-bottom: 4px;">{emoji} {item.get('title', 'Market Insight')}</div>
                    <div style="color: #cbd5e0; font-size: 13px; line-height: 1.4;">{item.get('description', '')}</div>
                </div>
                """

        # Generate top risks list
        risks_html = ""
        top_risks = report_data.get("top_risks", [])
        for risk in top_risks:
            risks_html += f"<li style='margin-bottom: 8px;'>{risk}</li>"
        if not risks_html:
            risks_html = "<li>No significant risks identified today.</li>"

        # Generate positive aspects list
        positives_html = ""
        positives = report_data.get("positive_aspects", [])
        for pos in positives:
            positives_html += f"<li style='margin-bottom: 8px;'>{pos}</li>"
        if not positives_html:
            positives_html = "<li>No specific highlights today.</li>"

        # Host URL for local references
        host_url = "http://localhost:8000"
        unsubscribe_url = f"{host_url}/api/subscriptions/unsubscribe-direct?email={email}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>DiversifyAI Portfolio Intelligence</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #0f172a; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e2e8f0;">
            <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background: #1e293b; margin: 30px auto; border-radius: 12px; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.04); border: 1px solid rgba(255, 255, 255, 0.05);">
                
                <!-- HEADER BANNER -->
                <tr>
                    <td align="center" style="background: linear-gradient(135deg, #4f46e5 0%, #1e1b4b 100%); padding: 30px 20px;">
                        <h1 style="margin: 0; color: #ffffff; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">🌌 DiversifyAI</h1>
                        <p style="margin: 5px 0 0 0; color: #c7d2fe; font-size: 14px; text-transform: uppercase; letter-spacing: 2px;">Daily Portfolio Intelligence</p>
                    </td>
                </tr>
                
                <!-- KEY METRICS PANEL -->
                <tr>
                    <td style="padding: 20px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td width="33%" align="center" style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 8px;">
                                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; margin-bottom: 5px;">Portfolio Value</div>
                                    <div style="color: #ffffff; font-size: 16px; font-weight: bold;">₹{total_value:,.2f}</div>
                                </td>
                                <td width="2%"></td>
                                <td width="31%" align="center" style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 8px;">
                                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; margin-bottom: 5px;">Health Score</div>
                                    <div style="color: {health_color}; font-size: 20px; font-weight: 800;">{health_score}<span style="font-size: 11px; color: #64748b;">/100</span></div>
                                </td>
                                <td width="2%"></td>
                                <td width="32%" align="center" style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 8px;">
                                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; margin-bottom: 5px;">Risk Score</div>
                                    <div style="color: {risk_color}; font-size: 20px; font-weight: 800;">{risk_score}<span style="font-size: 11px; color: #64748b;">/10</span></div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <!-- EXECUTIVE SUMMARY -->
                <tr>
                    <td style="padding: 0 20px 20px 20px;">
                        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 8px;">
                            <h3 style="margin-top: 0; color: #818cf8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Advisory Executive Summary</h3>
                            <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #cbd5e1;">{summary}</p>
                        </div>
                    </td>
                </tr>

                <!-- NEWS & RISK IMPACTS -->
                <tr>
                    <td style="padding: 0 20px 20px 20px;">
                        <h3 style="margin-top: 0; color: #ffffff; font-size: 16px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 8px; margin-bottom: 15px;">⚠️ Actionable Alerts & News Synthesis</h3>
                        {insights_html}
                    </td>
                </tr>

                <!-- BULLETED HIGHLIGHTS (PROS & CONS) -->
                <tr>
                    <td style="padding: 0 20px 20px 20px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td width="48%" valign="top" style="background: rgba(239, 68, 68, 0.02); border: 1px solid rgba(239, 68, 68, 0.1); padding: 15px; border-radius: 8px;">
                                    <h4 style="margin: 0 0 10px 0; color: #ef4444; font-size: 13px; text-transform: uppercase;">⚠️ Top Risks Detected</h4>
                                    <ul style="margin: 0; padding-left: 20px; color: #cbd5e1; font-size: 13px; line-height: 1.5;">
                                        {risks_html}
                                    </ul>
                                </td>
                                <td width="4%"></td>
                                <td width="48%" valign="top" style="background: rgba(16, 185, 129, 0.02); border: 1px solid rgba(16, 185, 129, 0.1); padding: 15px; border-radius: 8px;">
                                    <h4 style="margin: 0 0 10px 0; color: #10b981; font-size: 13px; text-transform: uppercase;">📈 Strong Diversifiers</h4>
                                    <ul style="margin: 0; padding-left: 20px; color: #cbd5e1; font-size: 13px; line-height: 1.5;">
                                        {positives_html}
                                    </ul>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <!-- ACTION BUTTON -->
                <tr>
                    <td align="center" style="padding: 10px 20px 30px 20px;">
                        <a href="{host_url}" target="_blank" style="background: #4f46e5; color: #ffffff; text-decoration: none; padding: 12px 30px; font-weight: bold; border-radius: 6px; font-size: 14px; display: inline-block; box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.4);">Launch Dashboard</a>
                    </td>
                </tr>

                <!-- FOOTER -->
                <tr>
                    <td align="center" style="background: #0f172a; padding: 25px 20px; border-top: 1px solid rgba(255, 255, 255, 0.05);">
                        <p style="margin: 0 0 10px 0; font-size: 12px; color: #64748b;">You are receiving this because you subscribed to daily reports on DiversifyAI.</p>
                        <p style="margin: 0; font-size: 12px; color: #64748b;">
                            <a href="{unsubscribe_url}" target="_blank" style="color: #ef4444; text-decoration: none;">Unsubscribe Alerts</a> | 
                            <a href="{host_url}" target="_blank" style="color: #818cf8; text-decoration: none; margin-left: 5px;">Manage Settings</a>
                        </p>
                        <p style="margin: 15px 0 0 0; font-size: 11px; color: #475569;">&copy; 2026 DiversifyAI Platform. Generative intelligence is advisory; verify all trades.</p>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        return html

    def send_daily_report(self, receiver_email: str, report_data: Dict[str, Any], total_value: float) -> bool:
        """
        Sends the beautifully formatted daily report to the target subscriber.
        """
        if not self.smtp_username or not self.smtp_password or not self.sender_email:
            logger.warning("SMTP credentials are not configured in environment variables. Email cannot be sent.")
            logger.info("Ensure SMTP_USERNAME, SMTP_PASSWORD, and SENDER_EMAIL are added to your .env file.")
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🌌 DiversifyAI Daily Intelligence Report — Health: {report_data.get('health_score', 'N/A')}/100"
        msg['From'] = self.sender_email
        msg['To'] = receiver_email

        # Render HTML and text versions
        html_content = self._render_html_template(receiver_email, report_data, total_value)
        text_content = f"""
        🌌 DiversifyAI Daily Intelligence Report
        ---------------------------------------
        Portfolio Total Value: ₹{total_value:,.2f}
        Health Score: {report_data.get('health_score', 0)}/100
        Risk Rating: {report_data.get('risk_score', 0.0)}/10.0
        
        Executive Summary:
        {report_data.get('executive_summary')}
        
        To see complete details, launch the web dashboard at http://localhost:8000
        """

        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        try:
            # Connect via SMTP with STARTTLS
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.set_debuglevel(0)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.sender_email, receiver_email, msg.as_string())
            server.quit()
            logger.info(f"Successfully sent daily advisor report email to {receiver_email}.")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch daily report email to {receiver_email}: {str(e)}")
            return False
