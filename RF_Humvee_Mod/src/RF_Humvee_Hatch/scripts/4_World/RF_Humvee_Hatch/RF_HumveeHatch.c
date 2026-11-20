// Люк на крыше. Положение люка = фаза источника анимации "HatchRoof"
// (source = "user" в config.cpp RF_Humvee — движок сам синхронизирует её с клиентами).

// Формат блока сохранения люка (OnStoreSave/OnStoreLoad ниже).
const int RF_HATCH_STORE_MAGIC = 1380337748; // 0x52464854 = "RFHT", метка нашего блока
const int RF_HATCH_STORE_VERSION = 1;        // v0 = один bool без метки (первые сборки)

modded class RF_Humvee
{
	static const string HATCH_SOURCE = "HatchRoof";
	static const string HATCH_SELECTION = "hatch_roof";

	protected bool m_RF_HatchOpen;

	// На машине — только действия снаружи (цель = крышка люка под курсором).
	// Действия из салона висят на игроке: modded PlayerBase ниже.
	override void SetActions()
	{
		super.SetActions();

		AddAction(ActionRFOpenHatchOutside);
		AddAction(ActionRFCloseHatchOutside);
	}

	bool RF_IsHatchOpen()
	{
		return GetAnimationPhase(HATCH_SOURCE) > 0.5;
	}

	// Вызывать только на сервере.
	void RF_SetHatchOpen(bool open)
	{
		m_RF_HatchOpen = open;

		float phase = 0;
		if (open)
			phase = 1;

		SetAnimationPhase(HATCH_SOURCE, phase);
	}

	// ------------------------------------------------------------ сохранение
	// Наш блок идёт в конце записи машины, после данных super:
	//   v0 (первые сборки): bool open
	//   v1 (сейчас):        bool open, int RF_HATCH_STORE_MAGIC, int RF_HATCH_STORE_VERSION
	// bool оставлен первым: у ParamsReadContext есть только Read, «отмотать» чтение
	// нельзя, поэтому v0 обязан быть началом v1. Новые поля будущих версий — только
	// после номера версии, первое поле (bool) не меняется никогда.
	override void OnStoreSave(ParamsWriteContext ctx)
	{
		super.OnStoreSave(ctx);

		int magic = RF_HATCH_STORE_MAGIC;
		int storeVersion = RF_HATCH_STORE_VERSION;
		ctx.Write(m_RF_HatchOpen);
		ctx.Write(magic);
		ctx.Write(storeVersion);
	}

	override bool OnStoreLoad(ParamsReadContext ctx, int version)
	{
		// ошибки в данных ванили и других модов обрабатываются как раньше
		if (!super.OnStoreLoad(ctx, version))
			return false;

		// version — версия хранилища игры, не наша. Наш блок машину не удаляет никогда.
		m_RF_HatchOpen = RF_HatchReadStore(ctx);
		return true;
	}

	// Возвращает сохранённое положение люка; при любой неясности — false (закрыт).
	protected bool RF_HatchReadStore(ParamsReadContext ctx)
	{
		bool open = false;
		if (!ctx.Read(open))
			return false; // нашего блока нет: машина сохранена без мода люка

		int magic = 0;
		if (!ctx.Read(magic))
			return open; // v0: в записи только bool, как в первых сборках

		if (magic != RF_HATCH_STORE_MAGIC)
		{
			// после bool лежит не наша метка: читаем чужие байты (сменился набор модов)
			RF_HatchStoreWarning("unknown data instead of hatch block");
			return false;
		}

		int storeVersion = 0;
		if (!ctx.Read(storeVersion) || storeVersion < 1)
		{
			RF_HatchStoreWarning("broken hatch block");
			return false;
		}

		// storeVersion > RF_HATCH_STORE_VERSION: запись сделана более новой сборкой.
		// bool по договорённости тот же, хвост новых полей не читаем (см. ARCHITECTURE_NOTES, H1).
		return open;
	}

	protected void RF_HatchStoreWarning(string reason)
	{
		Print("[RF_Humvee_Hatch] " + reason + ", hatch closed: " + GetType() + " at " + GetPosition().ToString());
	}

	override void AfterStoreLoad()
	{
		super.AfterStoreLoad();
		RF_SetHatchOpen(m_RF_HatchOpen);

		// после рестарта люк сразу стоит как был, а не открывается заново на глазах
		float phase = 0;
		if (m_RF_HatchOpen)
			phase = 1;
		SetAnimationPhaseNow(HATCH_SOURCE, phase);
	}
}

// Действия из салона регистрируются на игроке, как ванильные двери из салона.
// Обычный ввод «Действие» собирает действия цели под камерой и самого игрока; своя
// машина целью бывает не всегда (окно, открытый люк), на машине они могли теряться.
// Машину находит ActionCondition через GetCommand_Vehicle() и пропускает только RF_Humvee.
// Перегрузка с картой действий: её вызывает PlayerBase.InitializeActions, а SetActions()
// без параметров оставлен ванилью только для совместимости.
modded class PlayerBase
{
	override void SetActions(out TInputActionMap InputActionMap)
	{
		super.SetActions(InputActionMap);

		AddAction(ActionRFOpenHatchInVehicle, InputActionMap);
		AddAction(ActionRFCloseHatchInVehicle, InputActionMap);
	}
}

// Без регистрации здесь AddAction() не найдёт действия.
modded class ActionConstructor
{
	override void RegisterActions(TTypenameArray actions)
	{
		super.RegisterActions(actions);

		actions.Insert(ActionRFOpenHatchInVehicle);
		actions.Insert(ActionRFCloseHatchInVehicle);
		actions.Insert(ActionRFOpenHatchOutside);
		actions.Insert(ActionRFCloseHatchOutside);
	}
}
