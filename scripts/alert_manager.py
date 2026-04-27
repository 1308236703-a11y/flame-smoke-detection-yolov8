import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self, test_mode=True):
        self.test_mode = test_mode
        self.enable_sms = os.getenv('ENABLE_SMS', 'False').lower() == 'true'
        
        if not self.test_mode and self.enable_sms:
            try:
                from twilio.rest import Client
                account_sid = os.getenv('TWILIO_ACCOUNT_SID')
                auth_token = os.getenv('TWILIO_AUTH_TOKEN')
                self.twilio_client = Client(account_sid, auth_token)
                self.twilio_from = os.getenv('TWILIO_PHONE_NUMBER')
            except Exception as e:
                logger.warning(f"Twilio初始化失败: {e}，将使用测试模式")
                self.test_mode = True
        else:
            self.twilio_client = None
        
        self.alert_cooldown = {}  # 防止重复报警
        self.cooldown_duration = 300  # 5分钟冷却时间

    def send_sms_alert(self, phone_number, alert_type, flame_count, smoke_count, 
                       confidence, image_path):
        """发送短信报警"""
        message = f"[火焰烟雾检测系统]\n类型: {alert_type}\n火焰数: {flame_count}\n烟雾数: {smoke_count}\n置信度: {confidence:.2f}\n时间: {datetime.now().strftime('%H:%M:%S')}"
        
        if self.test_mode:
            logger.info(f"[测试模式] SMS报警:\n收件人: {phone_number}\n内容: {message}")
            return True
        
        try:
            if self.twilio_client:
                self.twilio_client.messages.create(
                    body=message,
                    from_=self.twilio_from,
                    to=phone_number
                )
                logger.info(f"短信已发送到 {phone_number}")
                return True
        except Exception as e:
            logger.error(f"短信发送失败: {e}")
            return False

    def should_alert(self, alert_key, flame_count, smoke_count, confidence, 
                     min_confidence=0.6):
        """判断是否应该发送报警（包含冷却检查）"""
        # 检查置信度阈值
        if confidence < min_confidence:
            return False
        
        # 检查冷却时间
        if alert_key in self.alert_cooldown:
            last_alert_time = self.alert_cooldown[alert_key]
            if datetime.now() - last_alert_time < timedelta(seconds=self.cooldown_duration):
                logger.debug(f"报警冷却中: {alert_key}")
                return False
        
        # 检查是否有检测到火焰或烟雾
        if flame_count > 0 or smoke_count > 0:
            self.alert_cooldown[alert_key] = datetime.now()
            return True
        
        return False

    def trigger_alert(self, detection_id, flame_count, smoke_count, confidence, 
                     image_path, phone_number=None):
        """触发报警"""
        if phone_number is None:
            phone_number = os.getenv('ALERT_PHONE_NUMBER', '+1234567890')
        
        alert_type = "火焰" if flame_count > 0 else "烟雾"
        
        if self.should_alert(f"alert_{detection_id}", flame_count, smoke_count, confidence):
            success = self.send_sms_alert(
                phone_number, alert_type, flame_count, smoke_count, 
                confidence, image_path
            )
            logger.info(f"报警触发: 类型={alert_type}, 检测ID={detection_id}, 状态={'成功' if success else '失败'}")
            return success
        
        return False

    def log_alert_event(self, detection_id, alert_type, message):
        """记录报警事件"""
        logger.warning(f"[ALERT] Detection ID: {detection_id}, Type: {alert_type}, Message: {message}")
