// Машина: ванильный M1025 (Offroad_02) с люком стрелка. Двери, капот, багажник, салон, места, колёса — ванильные.
// Верхняя часть кузова своя: деталь RF_HumveeHatch (крыша и потолок с отверстием, задние наплывы, кольцо и крышка
// люка) вместо скрытых ванильных camo_roof и camo_interior_roof. У каждого клиента она своя, локальная,
// прикреплена к машине, как ванильный свет фар. Открыт ли люк, сервер передаёт синхронизируемой переменной;
// действия и сохранение положения — в аддоне RF_Humvee_Hatch.

class RF_Humvee extends Offroad_02
{
	static const string HATCH_SOURCE = "HatchRoof";
	// центр кольца люка на крыше в координатах модели M1025 (см. build_mod.py: HATCH_X/HATCH_Z, ROOF_Y)
	static const vector HATCH_POS = "-0.12 1.84 -0.30";

	protected bool m_RF_HatchOpen;
	protected EntityAI m_RF_Hatch;

	void RF_Humvee()
	{
		RegisterNetSyncVariableBool("m_RF_HatchOpen");
	}

	string RF_HatchType()
	{
		return "RF_HumveeHatch";
	}

	override void EEInit()
	{
		super.EEInit();

		if (!g_Game.IsDedicatedServer())
			RF_CreateHatch();
	}

	override void EEDelete(EntityAI parent)
	{
		super.EEDelete(parent);

		if (m_RF_Hatch)
			m_RF_Hatch.Delete();
	}

	protected void RF_CreateHatch()
	{
		m_RF_Hatch = EntityAI.Cast(g_Game.CreateObjectEx(RF_HatchType(), GetPosition(), ECE_LOCAL));
		if (!m_RF_Hatch)
			return;

		// Модель машины игра разворачивает на 180° относительно файла P3D (водитель на -X, перёд на +Z), а прикреплённую
		// деталь — нет: без разворота крышка люка открывалась петлями вперёд и стояла не над ванильной крышкой.
		// Если движок сместил начало модели детали к центру её рамки, точка rf_origin (начало модели) покажет сдвиг.
		vector origin = m_RF_Hatch.GetMemoryPointPos("rf_origin");
		m_RF_Hatch.SetOrientation("180 0 0");
		m_RF_Hatch.SetPosition(Vector(origin[0], -origin[1], origin[2]));
		AddChild(m_RF_Hatch, -1);
		Update();
		m_RF_Hatch.SetAnimationPhaseNow(HATCH_SOURCE, RF_HatchPhase());
	}

	protected float RF_HatchPhase()
	{
		if (m_RF_HatchOpen)
			return 1;

		return 0;
	}

	override void OnVariablesSynchronized()
	{
		super.OnVariablesSynchronized();

		if (m_RF_Hatch)
			m_RF_Hatch.SetAnimationPhase(HATCH_SOURCE, RF_HatchPhase());
	}

	bool RF_IsHatchOpen()
	{
		return m_RF_HatchOpen;
	}

	// Вызывать только на сервере.
	void RF_SetHatchOpen(bool open)
	{
		m_RF_HatchOpen = open;
		SetSynchDirty();
	}

	// игрок стоит на крыше рядом с люком: снаружи люк открывают и закрывают с крыши
	bool RF_IsAtHatch(PlayerBase player)
	{
		vector p = WorldToModel(player.GetPosition());
		if (p[1] < HATCH_POS[1] - 0.3)
			return false;

		return vector.Distance(Vector(p[0], 0, p[2]), Vector(HATCH_POS[0], 0, HATCH_POS[2])) < 1.5;
	}
}

class RF_Humvee_Desert extends RF_Humvee
{
	override string RF_HatchType()
	{
		return "RF_HumveeHatch_Desert";
	}

	// детали бежевой окраски, как у ванильного Offroad_02_Beige
	override void OnDebugSpawn()
	{
		SpawnUniversalParts();
		SpawnAdditionalItems();
		FillUpCarFluids();

		GameInventory inventory = GetInventory();
		for (int i = 0; i < 4; i++)
			inventory.CreateInInventory("Offroad_02_Wheel");

		inventory.CreateInInventory("Offroad_02_Door_1_1_Beige");
		inventory.CreateInInventory("Offroad_02_Door_1_2_Beige");
		inventory.CreateInInventory("Offroad_02_Door_2_1_Beige");
		inventory.CreateInInventory("Offroad_02_Door_2_2_Beige");
		inventory.CreateInInventory("Offroad_02_Trunk_Beige");
		inventory.CreateInInventory("Offroad_02_Hood_Beige");

		inventory.CreateInInventory("Offroad_02_Wheel");
		inventory.CreateInInventory("Offroad_02_Wheel");
	}
}
