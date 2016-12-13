# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from ulakbus.models import User
from .general import fake

__author__ = 'Ali Riza Keles'


def new_user(username=None, password=None, superuser=False):
    """
    Rastgele verileri ve parametre olarak verilen verileri
    kullanarak yeni değerlendirme notu kaydı oluşturup kaydeder.

    Args:
        username (str): Kullanıcı adı
        password (str): Şifre
        superuser (bool): Süper kullanıcı

    Returns:
        Kullanıcı kaydı

    """
    
    user = User(
        name=fake.first_name(),
        surname=fake.last_name(),
        username=username or fake.user_name(),
        password=password or fake.password(),
        superuser=superuser
    )
    user.save()
    return user
