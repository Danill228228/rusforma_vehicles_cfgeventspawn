// ТЕСТОВЫЙ СПАВН: каждому новому персонажу в 7 м перед ним ставится полностью собранный RF_Humvee.
// Вставьте функцию в mpmissions/dayzOffline.chernarusplus/init.c внутрь class CustomMission
// и вызовите из StartingEquipSetup (см. ниже). После теста — уберите.

	void RF_SpawnTestHumvee(PlayerBase player)
	{
		vector pos = player.GetPosition() + player.GetDirection() * 7;
		pos[1] = GetGame().SurfaceY(pos[0], pos[2]);

		Car car = Car.Cast(GetGame().CreateObjectEx("RF_Humvee", pos, ECE_PLACE_ON_SURFACE));
		if (!car)
		{
			Print("[RF_Humvee] Не удалось создать RF_Humvee — смотрите ошибки конфига/модели выше в логе");
			return;
		}

		// Поворот после создания (SetOrientation) до клиента не доходит: машина у игрока и на сервере стоит по-разному,
		// и сервер отменяет посадку. Машина ставится как есть.
		// Колёса, двери, капот, багажник, аккумулятор, свечи, фары и жидкости — как у ванильного M1025.
		car.OnDebugSpawn();

		Print("[RF_Humvee] Тестовая машина создана в " + pos.ToString());
	}

// В существующем методе StartingEquipSetup(PlayerBase player, bool clothesChosen) добавьте первой строкой:
//		RF_SpawnTestHumvee(player);
