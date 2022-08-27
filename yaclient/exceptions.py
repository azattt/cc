"""Here I will define YaClient module exceptions"""


class LicenseNotApprovedError(Exception):
    """Stream DRM license not approved"""


class WrongCredentialsError(Exception):
    """Occurs when you try to login with false credentials"""


class WrongCaptchaAnswerError(Exception):
    """Wrong captcha passed"""


class WrongChallengeAnswerError(Exception):
    """Wrong sms-code"""
