from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'maze_bot'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(),
    install_requires=['setuptools'],
    zip_safe=True,
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.py')),
        (os.path.join('share', package_name, 'worlds'),
            glob('worlds/*.world')),
        (os.path.join('share', package_name, 'urdf'),
            glob('urdf/*.urdf')),
        (os.path.join('share', package_name, 'rviz'),
            glob('rviz/*.rviz')),
    ],
    entry_points={
        'console_scripts': [
            'controller = maze_bot.controller:main',
        ],
    },
)
