from setuptools import find_packages, setup

setup(name='sgbridgebot',
      version='0.1-alpha',
      description='A Telegram bot that allows users to play floating bridge',
      url='http://github.com/zuzivian/sgbridgebot',
      author='Nathaniel Wong',
      author_email='rubikcode@gmail.com',
      license='MIT',
      packages=find_packages(include=['sgbridgebot', 'sgbridgebot.*']),
      zip_safe=False)
