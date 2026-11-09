// =====================================================================================
// HatchP0 — прототип P0: стрелок в люке ванильного Offroad_02.
//
// Привязка к машине повторяет схему, уже проверенную в моде CrewFire на DayZ 1.30
// (ветка claude/dayz-vehicle-shooting-animation-s15all): гравитация и коллизия капсулы
// выключены, игрок привязан LinkToLocalSpaceOf и перепривязывается, если капсулу сдвинуло.
//
// Вопросы теста:
//   T1  Держится ли игрок в точке люка стоя и на 20/40/60 км/ч.
//   T2  Работает ли штатное оружие в люке; с какими углами выстрел безопасен.
//   T3  Удерживает ли движок игрока на крыше сам, без привязки (animPhysDetachSpeed в конфиге).
//   T4  Как выглядит стрелок «по пояс в люке» и какая глубина правильная.
//   T5  Не уходит ли игрок с точки при поворотах, смене стойки и стрельбе.
//
// ЗАЩИТА ОТ ВЫЛЕТА: выстрел, который сразу попадает в машину, к которой привязан игрок,
// роняет игру (и сервер) — это выяснено в CrewFire. Поэтому, пока игрок привязан,
// стрельба запрещена, если ствол опущен ниже MIN_AIM_UD, голова слишком близко к крыше
// или стойка не «стоя».
//
// Работает только в DayZDiag (DIAG_DEVELOPER). Вывод — в скрипт-лог с меткой [HATCHP0].
// Управление: prototype/README.md
// =====================================================================================

const int HATCHP0_RPC = 4761536;

enum HatchP0Cmd
{
	NONE,
	LINK,			// поставить в точку люка и привязать (схема CrewFire)
	PLACE,			// поставить на крышу без привязки (тест T3)
	UNLINK,			// отвязать и сбросить все режимы
	AP_20,			// автопилот 20 км/ч
	AP_40,			// автопилот 40 км/ч
	AP_60,			// автопилот 60 км/ч
	AP_STOP,		// плавная остановка
	HATCH_MODE,		// переключить «на крыше» / «в люке» (глубина HATCH_DEPTH)
	LOCK_MOVE,		// вкл/выкл блокировку ходьбы
	DUMP,			// подробный срез состояния, включая других игроков рядом
	HEIGHT_UP,		// точка крепления выше на 0.1 м
	HEIGHT_DOWN		// точка крепления ниже на 0.1 м
};

// -------------------------------------------------------------------------------------
// Лог и сообщения
// -------------------------------------------------------------------------------------
class HatchP0Log
{
	static string Side()
	{
		if (!GetGame().IsMultiplayer())
			return "OFFLINE";
		if (GetGame().IsDedicatedServer())
			return "SERVER";
		return "CLIENT";
	}

	static void Msg(string text)
	{
		Print("[HATCHP0][" + Side() + "] " + text);
	}

	// В лог и в чат (чат только там, где есть интерфейс)
	static void Notify(string text)
	{
		Msg(text);
		if (!GetGame().IsDedicatedServer())
			GetGame().Chat("[HatchP0] " + text, "colorAction");
	}

	static string Name(IEntity ent)
	{
		if (!ent)
			return "none";

		Object obj = Object.Cast(ent);
		if (obj)
			return obj.GetType();

		return ent.ClassName();
	}

	static string CmdName(int id)
	{
		switch (id)
		{
			case DayZPlayerConstants.COMMANDID_MOVE:		return "MOVE";
			case DayZPlayerConstants.COMMANDID_ACTION:		return "ACTION";
			case DayZPlayerConstants.COMMANDID_FALL:		return "FALL";
			case DayZPlayerConstants.COMMANDID_DAMAGE:		return "DAMAGE";
			case DayZPlayerConstants.COMMANDID_VEHICLE:		return "VEHICLE";
			case DayZPlayerConstants.COMMANDID_CLIMB:		return "CLIMB";
			case DayZPlayerConstants.COMMANDID_SCRIPT:		return "SCRIPT";
			case DayZPlayerConstants.COMMANDID_UNCONSCIOUS:	return "UNCONSCIOUS";
			case DayZPlayerConstants.COMMANDID_DEATH:		return "DEATH";
		}

		return id.ToString();
	}
}

// -------------------------------------------------------------------------------------
// Автопилот: толкает машину вперёд с заданной скоростью без водителя.
// Только на сервере (или в офлайне). Автостоп через MAX_DURATION секунд.
// -------------------------------------------------------------------------------------
class HatchP0Autopilot
{
	protected static ref HatchP0Autopilot s_Instance;

	static const float MAX_DURATION = 15.0;	// с
	static const float MAX_ACCEL    = 4.0;	// м/с², плавный разгон и торможение

	protected CarScript	m_Car;
	protected float		m_TargetSpeed;		// м/с
	protected float		m_Elapsed;
	protected bool		m_Active;

	static HatchP0Autopilot Get()
	{
		if (!s_Instance)
		{
			s_Instance = new HatchP0Autopilot();
			GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(s_Instance.OnUpdate);
		}

		return s_Instance;
	}

	void Start(CarScript car, float kmh)
	{
		if (!car)
		{
			HatchP0Log.Notify("Автопилот: машина не найдена");
			return;
		}

		m_Car = car;
		m_TargetSpeed = kmh / 3.6;
		m_Elapsed = 0;
		m_Active = true;
		HatchP0Log.Notify(string.Format("Автопилот: разгон до %1 км/ч, автостоп через %2 с. Нужна прямая дорога!", kmh, MAX_DURATION));
	}

	void Stop()
	{
		if (!m_Active)
			return;

		m_TargetSpeed = 0;
		HatchP0Log.Notify("Автопилот: торможение");
	}

	void OnUpdate(float dt)
	{
		if (!m_Active)
			return;

		if (!m_Car)
		{
			m_Active = false;
			return;
		}

		m_Elapsed += dt;
		if (m_Elapsed > MAX_DURATION && m_TargetSpeed > 0)
		{
			m_TargetSpeed = 0;
			HatchP0Log.Notify("Автопилот: время вышло, торможение");
		}

		vector vel = GetVelocity(m_Car);
		vector fwd = m_Car.GetDirection();
		fwd[1] = 0;
		fwd.Normalize();

		float curSpeed = vector.Dot(vel, fwd);
		float maxDelta = MAX_ACCEL * dt;
		float nextSpeed = curSpeed + Math.Clamp(m_TargetSpeed - curSpeed, -maxDelta, maxDelta);

		vector newVel = fwd * nextSpeed;
		newVel[1] = vel[1];

		dBodyActive(m_Car, ActiveState.ACTIVE);
		SetVelocity(m_Car, newVel);

		if (m_TargetSpeed <= 0 && nextSpeed < 0.3)
		{
			SetVelocity(m_Car, Vector(0, vel[1], 0));
			m_Active = false;
			HatchP0Log.Notify("Автопилот: остановлен");
		}
	}
}

// -------------------------------------------------------------------------------------
// Основная логика теста
// -------------------------------------------------------------------------------------
class HatchP0
{
	static const float	SEARCH_RADIUS	= 15.0;	// м, поиск Offroad_02 вокруг игрока
	static const int	LOG_INTERVAL	= 500;	// мс, период строк TICK
	static const int	LINK_GRACE		= 1000;	// мс после привязки, в течение которых не проверяем LINK_LOST
	static const float	HATCH_DEPTH		= 1.0;	// м, на сколько ниже крыши стоят ноги в режиме «в люке»
	static const float	PIN_DISTANCE	= 0.03;	// м, сдвиг капсулы, после которого перепривязываем (как в CrewFire)
	static const float	MAX_STRAY		= 0.8;	// м, дальше — игрока что-то вытолкнуло, только сообщаем
	static const float	MIN_AIM_UD		= -5.0;	// град, ниже — стрельба запрещена (ствол смотрит в машину)
	static const float	MIN_HEAD_ABOVE	= 0.35;	// м, голова ниже этого над крышей — стрельба запрещена

	// ---------- поиск машины ----------
	static CarScript FindCar(PlayerBase player)
	{
		if (player.m_HatchP0Car)
			return player.m_HatchP0Car;

		array<Object> objs = new array<Object>;
		GetGame().GetObjectsAtPosition(player.GetPosition(), SEARCH_RADIUS, objs, null);

		CarScript best;
		float bestDist = 1000000;
		foreach (Object obj : objs)
		{
			Offroad_02 car = Offroad_02.Cast(obj);
			if (!car)
				continue;

			float dist = vector.Distance(car.GetPosition(), player.GetPosition());
			if (dist < bestDist)
			{
				bestDist = dist;
				best = car;
			}
		}

		return best;
	}

	// ---------- точка люка на крыше в пространстве модели ----------
	static bool GetRoofPointMS(CarScript car, PlayerBase player, out vector pointMS, out string method)
	{
		vector box[2];
		if (!car.GetCollisionBox(box))
			return false;

		vector boxMin = box[0];
		vector boxMax = box[1];

		vector basePos;
		if (car.MemoryPointExists("dmgZone_roof"))
		{
			basePos = car.GetMemoryPointPos("dmgZone_roof");
			method = "memorypoint dmgZone_roof";
		}
		else
		{
			basePos = (boxMin + boxMax) * 0.5;
			method = "центр collision box";
		}

		float roofY = boxMax[1];
		string heightMethod = "верх collision box";

		// Ищем реальную поверхность крыши лучом сверху вниз по геометрии машины
		vector rayFrom = car.ModelToWorld(Vector(basePos[0], boxMax[1] + 1.0, basePos[2]));
		vector rayTo   = car.ModelToWorld(Vector(basePos[0], boxMin[1], basePos[2]));
		vector hitPos;
		vector hitDir;
		int hitComponent;
		set<Object> results = new set<Object>;
		if (DayZPhysics.RaycastRV(rayFrom, rayTo, hitPos, hitDir, hitComponent, results, car, player, false, false, ObjIntersectGeom, 0.0))
		{
			vector hitMS = car.WorldToModel(hitPos);
			roofY = hitMS[1];
			heightMethod = "луч по Geometry LOD";
		}

		pointMS = Vector(basePos[0], roofY, basePos[2]);
		method = method + ", высота: " + heightMethod;
		return true;
	}

	// ---------- привязка с сохранением текущего поворота игрока относительно машины ----------
	static void Pin(PlayerBase player)
	{
		CarScript car = player.m_HatchP0Car;
		if (!car)
			return;

		vector carTm[4];
		vector playerTm[4];
		vector localTm[4];
		car.GetTransform(carTm);
		player.GetTransform(playerTm);
		Math3D.MatrixInvMultiply4(carTm, playerTm, localTm);
		localTm[3] = player.m_HatchP0TargetMS;

		player.UnlinkFromLocalSpace();
		player.LinkToLocalSpaceOf(car, localTm);
	}

	// ---------- поставить в точку люка (с привязкой или без) ----------
	static void PlaceOnRoof(PlayerBase player, CarScript car, bool link)
	{
		if (!car)
		{
			HatchP0Log.Notify("Рядом нет Offroad_02 (радиус 15 м)");
			return;
		}

		if (player.GetCommand_Vehicle())
		{
			HatchP0Log.Notify("Сначала выйдите из машины");
			return;
		}

		vector roofMS;
		string method;
		if (!GetRoofPointMS(car, player, roofMS, method))
		{
			HatchP0Log.Notify("Не удалось вычислить точку на крыше");
			return;
		}

		float depth = 0;
		if (player.m_HatchP0HatchMode)
			depth = HATCH_DEPTH;

		vector feetMS = roofMS;
		feetMS[1] = roofMS[1] + 0.02 - depth + player.m_HatchP0HeightOffset;

		if (player.m_HatchP0Linked)
		{
			player.UnlinkFromLocalSpace();
			player.m_HatchP0Linked = false;
		}

		// Поставить игрока в точку, лицом вперёд по машине
		vector carTm[4];
		car.GetTransform(carTm);
		vector localTm[4];
		localTm[0] = "1 0 0";
		localTm[1] = "0 1 0";
		localTm[2] = "0 0 1";
		localTm[3] = feetMS;
		vector worldTm[4];
		Math3D.MatrixMultiply4(carTm, localTm, worldTm);

		player.SetPosition(worldTm[3]);
		vector carOri = car.GetOrientation();
		player.SetOrientation(Vector(carOri[0], 0, 0));

		player.m_HatchP0Car = car;
		player.m_HatchP0TargetMS = feetMS;
		player.m_HatchP0RoofY = roofMS[1];
		player.m_HatchP0LinkLostReported = false;
		player.m_HatchP0DriftReported = false;
		player.m_HatchP0LinkTime = GetGame().GetTime();

		string mode = "PLACE (без привязки)";
		if (link)
		{
			// Схема CrewFire: без гравитации и коллизии капсула не выталкивается из машины
			player.PhysicsEnableGravity(false);
			player.PhysicsSetSolid(false);
			HumanCommandMove hcm = player.GetCommand_Move();
			if (hcm)
				hcm.ForceStance(DayZPlayerConstants.STANCEIDX_ERECT);

			player.LinkToLocalSpaceOf(car, localTm);
			player.m_HatchP0Linked = true;
			SetMoveLock(player, true);
			mode = "LINK";
		}
		else
		{
			player.PhysicsEnableGravity(true);
			player.PhysicsSetSolid(true);
		}

		HatchP0Log.Notify(string.Format("%1: ноги(MS)=%2, крыша Y=%3, «в люке»=%4, доп. смещение=%5 м, способ: %6",
			mode, feetMS, roofMS[1], player.m_HatchP0HatchMode, player.m_HatchP0HeightOffset, method));
		LogStatus(player, "AFTER_" + mode);
	}

	static void Relink(PlayerBase player)
	{
		if (!player.m_HatchP0Car)
			return;

		bool wasLinked = player.m_HatchP0Linked;
		PlaceOnRoof(player, player.m_HatchP0Car, wasLinked);
	}

	// ---------- отвязать и сбросить режимы ----------
	static void Unlink(PlayerBase player)
	{
		SetMoveLock(player, false);

		if (player.m_HatchP0Linked)
		{
			player.UnlinkFromLocalSpace();
			player.m_HatchP0Linked = false;
		}

		player.PhysicsSetSolid(true);
		player.PhysicsEnableGravity(true);

		LogStatus(player, "BEFORE_RESET");
		player.m_HatchP0Car = null;
		player.m_HatchP0HatchMode = false;
		player.m_HatchP0HeightOffset = 0;
		HatchP0Log.Notify("Отвязан, режимы сброшены");
	}

	static void ToggleHatchMode(PlayerBase player)
	{
		player.m_HatchP0HatchMode = !player.m_HatchP0HatchMode;
		HatchP0Log.Notify(string.Format("Режим «в люке» (ноги на %1 м ниже крыши): %2", HATCH_DEPTH, player.m_HatchP0HatchMode));
		Relink(player);
	}

	// ---------- блокировка ходьбы ----------
	static void SetMoveLock(PlayerBase player, bool enable)
	{
		if (player.m_HatchP0MoveLocked == enable)
			return;

		player.m_HatchP0MoveLocked = enable;

		HumanInputController hic = player.GetInputController();
		if (!hic)
			return;

		if (enable)
			hic.OverrideMovementSpeed(HumanInputControllerOverrideType.ENABLED, 0);
		else
			hic.OverrideMovementSpeed(HumanInputControllerOverrideType.DISABLED, 0);
	}

	static void ToggleMoveLock(PlayerBase player)
	{
		SetMoveLock(player, !player.m_HatchP0MoveLocked);
		HatchP0Log.Notify(string.Format("Блокировка ходьбы: %1", player.m_HatchP0MoveLocked));
	}

	static void ChangeHeight(PlayerBase player, float delta)
	{
		player.m_HatchP0HeightOffset = player.m_HatchP0HeightOffset + delta;
		HatchP0Log.Notify(string.Format("Доп. смещение по высоте: %1 м", player.m_HatchP0HeightOffset));
		Relink(player);
	}

	// ---------- защита от вылета: можно ли сейчас стрелять ----------
	static float HeadAboveRoof(PlayerBase player)
	{
		if (!player.m_HatchP0Car)
			return 0;

		vector headWS = player.GetBonePositionWS(player.GetBoneIndexByName("Head"));
		vector headMS = player.m_HatchP0Car.WorldToModel(headWS);
		return headMS[1] - player.m_HatchP0RoofY;
	}

	static bool IsFireBlocked(PlayerBase player, out string reason)
	{
		if (!player.m_HatchP0Linked)
			return false;

		HumanMovementState hms = new HumanMovementState();
		player.GetMovementState(hms);
		if (hms.m_iStanceIdx != DayZPlayerConstants.STANCEIDX_ERECT && hms.m_iStanceIdx != DayZPlayerConstants.STANCEIDX_RAISEDERECT)
		{
			reason = "стойка не «стоя»";
			return true;
		}

		HumanCommandWeapons hcw = player.GetCommandModifier_Weapons();
		if (!hcw)
		{
			reason = "нет данных о прицеле";
			return true;
		}

		float aimUD = hcw.GetBaseAimingAngleUD();
		if (aimUD < MIN_AIM_UD)
		{
			reason = string.Format("ствол опущен: %1° < %2°", aimUD, MIN_AIM_UD);
			return true;
		}

		float headAbove = HeadAboveRoof(player);
		if (headAbove < MIN_HEAD_ABOVE)
		{
			reason = string.Format("голова над крышей %1 м < %2 м", headAbove, MIN_HEAD_ABOVE);
			return true;
		}

		return false;
	}

	static void ReportFireBlocked(PlayerBase player, string reason)
	{
		int now = GetGame().GetTime();
		if (now - player.m_HatchP0LastBlockLog < 1000)
			return;

		player.m_HatchP0LastBlockLog = now;
		HatchP0Log.Notify("Выстрел заблокирован: " + reason);
	}

	// ---------- состояние в лог ----------
	static void LogStatus(PlayerBase player, string tag)
	{
		CarScript car = player.m_HatchP0Car;
		if (!car)
			car = FindCar(player);

		string carInfo = "car=none";
		if (car)
		{
			vector posMS = car.WorldToModel(player.GetPosition());
			float speed = GetVelocity(car).Length() * 3.6;
			float drift = vector.Distance(posMS, player.m_HatchP0TargetMS);
			carInfo = string.Format("speed=%1kmh posMS=%2 drift=%3m", speed, posMS, drift);
		}

		bool raised = false;
		HumanInputController hic = player.GetInputController();
		if (hic)
			raised = hic.IsWeaponRaised();

		float aimUD = 0;
		HumanCommandWeapons hcw = player.GetCommandModifier_Weapons();
		if (hcw)
			aimUD = hcw.GetBaseAimingAngleUD();

		HumanMovementState hms = new HumanMovementState();
		player.GetMovementState(hms);

		HatchP0Log.Msg(string.Format("%1 cmd=%2 linkedEnt=%3 floorEnt=%4 slidingOff=%5 parent=%6 inVehicle=%7 raised=%8 %9",
			tag,
			HatchP0Log.CmdName(player.GetCurrentCommandID()),
			HatchP0Log.Name(player.PhysicsGetLinkedEntity()),
			HatchP0Log.Name(player.PhysicsGetFloorEntity()),
			player.PhysicsWasSlidingOffLinkedEntity(),
			HatchP0Log.Name(player.GetParent()),
			player.IsInVehicle(),
			raised,
			carInfo));

		HatchP0Log.Msg(string.Format("    testLinked=%1 hatchMode=%2 moveLock=%3 solid=%4 stance=%5 aimUD=%6 headAboveRoof=%7m pins=%8",
			player.m_HatchP0Linked,
			player.m_HatchP0HatchMode,
			player.m_HatchP0MoveLocked,
			player.PhysicsIsSolid(),
			hms.m_iStanceIdx,
			aimUD,
			HeadAboveRoof(player),
			player.m_HatchP0PinCount));
	}

	static void Dump(PlayerBase player)
	{
		LogStatus(player, "DUMP");
		HatchP0Log.Msg(string.Format("DUMP config Offroad_02 animPhysDetachSpeed=%1", GetGame().ConfigGetFloat("CfgVehicles Offroad_02 animPhysDetachSpeed")));

		// Другие игроки рядом — для проверки со второго клиента
		array<Object> objs = new array<Object>;
		GetGame().GetObjectsAtPosition(player.GetPosition(), 30, objs, null);
		foreach (Object obj : objs)
		{
			PlayerBase other = PlayerBase.Cast(obj);
			if (!other || other == player)
				continue;

			LogStatus(other, "DUMP_OTHER");
		}

		HatchP0Log.Notify("Состояние записано в лог");
	}

	// ---------- каждый шаг симуляции игрока (сервер и клиент-владелец) ----------
	static void OnPlayerTick(PlayerBase player, int commandID)
	{
		if (!player.m_HatchP0Car)
			return;

		int now = GetGame().GetTime();

		if (player.m_HatchP0Linked)
		{
			// Смерть, потеря сознания, вода: ничего не должно держать тело на машине (как в CrewFire)
			if (commandID != DayZPlayerConstants.COMMANDID_MOVE && commandID != DayZPlayerConstants.COMMANDID_ACTION && commandID != DayZPlayerConstants.COMMANDID_MELEE && commandID != DayZPlayerConstants.COMMANDID_MELEE2)
			{
				LogStatus(player, "EVENT_COMMAND_CHANGED");
				Unlink(player);
				return;
			}

			// Смена стойки и повороты сдвигают капсулу: возвращаем в точку (как в CrewFire)
			vector posMS = player.m_HatchP0Car.WorldToModel(player.GetPosition());
			float stray = vector.Distance(posMS, player.m_HatchP0TargetMS);
			if (stray > PIN_DISTANCE && stray < MAX_STRAY)
			{
				Pin(player);
				player.m_HatchP0PinCount++;
			}
			else if (stray >= MAX_STRAY && !player.m_HatchP0DriftReported)
			{
				player.m_HatchP0DriftReported = true;
				LogStatus(player, "EVENT_DRIFT");
			}

			if (!player.m_HatchP0LinkLostReported && now - player.m_HatchP0LinkTime > LINK_GRACE)
			{
				if (player.GetParent() != player.m_HatchP0Car && player.PhysicsGetLinkedEntity() != player.m_HatchP0Car)
				{
					player.m_HatchP0LinkLostReported = true;
					LogStatus(player, "EVENT_LINK_LOST");
				}
			}
		}

		if (now - player.m_HatchP0LastLog >= LOG_INTERVAL)
		{
			player.m_HatchP0LastLog = now;
			LogStatus(player, "TICK");
		}
	}

	// ---------- команда с клавиатуры (клиент или офлайн) ----------
	static void Request(int cmd)
	{
		PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
		if (!player)
			return;

		CarScript car = FindCar(player);

		if (GetGame().IsMultiplayer())
		{
			int low = 0;
			int high = 0;
			if (car)
				car.GetNetworkID(low, high);

			GetGame().RPCSingleParam(player, HATCHP0_RPC, new Param3<int, int, int>(cmd, low, high), true);
		}

		Execute(player, cmd, car);
	}

	// ---------- выполнение команды (на сервере и у клиента-владельца) ----------
	static void Execute(PlayerBase player, int cmd, CarScript car)
	{
		if (!car)
			car = player.m_HatchP0Car;

		// В офлайне IsServer() может быть false — ванильная проверка: IsServer() || !IsMultiplayer()
		bool isServer = GetGame().IsServer() || !GetGame().IsMultiplayer();

		switch (cmd)
		{
			case HatchP0Cmd.LINK:
				PlaceOnRoof(player, car, true);
				break;
			case HatchP0Cmd.PLACE:
				PlaceOnRoof(player, car, false);
				break;
			case HatchP0Cmd.UNLINK:
				Unlink(player);
				break;
			case HatchP0Cmd.AP_20:
				if (isServer)
					HatchP0Autopilot.Get().Start(car, 20);
				break;
			case HatchP0Cmd.AP_40:
				if (isServer)
					HatchP0Autopilot.Get().Start(car, 40);
				break;
			case HatchP0Cmd.AP_60:
				if (isServer)
					HatchP0Autopilot.Get().Start(car, 60);
				break;
			case HatchP0Cmd.AP_STOP:
				if (isServer)
					HatchP0Autopilot.Get().Stop();
				break;
			case HatchP0Cmd.HATCH_MODE:
				ToggleHatchMode(player);
				break;
			case HatchP0Cmd.LOCK_MOVE:
				ToggleMoveLock(player);
				break;
			case HatchP0Cmd.DUMP:
				Dump(player);
				break;
			case HatchP0Cmd.HEIGHT_UP:
				ChangeHeight(player, 0.1);
				break;
			case HatchP0Cmd.HEIGHT_DOWN:
				ChangeHeight(player, -0.1);
				break;
		}
	}
}

// -------------------------------------------------------------------------------------
// Состояние теста на игроке + приём команд на сервере
// -------------------------------------------------------------------------------------
modded class PlayerBase
{
	CarScript	m_HatchP0Car;
	bool		m_HatchP0Linked;
	bool		m_HatchP0HatchMode;
	bool		m_HatchP0MoveLocked;
	bool		m_HatchP0LinkLostReported;
	bool		m_HatchP0DriftReported;
	float		m_HatchP0HeightOffset;
	float		m_HatchP0RoofY;
	vector		m_HatchP0TargetMS;
	int			m_HatchP0LastLog;
	int			m_HatchP0LastBlockLog;
	int			m_HatchP0LinkTime;
	int			m_HatchP0PinCount;

	override void CommandHandler(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
	{
		super.CommandHandler(pDt, pCurrentCommandID, pCurrentCommandFinished);

#ifdef DIAG_DEVELOPER
		HatchP0.OnPlayerTick(this, pCurrentCommandID);
#endif
	}

	override void OnRPC(PlayerIdentity sender, int rpc_type, ParamsReadContext ctx)
	{
		super.OnRPC(sender, rpc_type, ctx);

#ifdef DIAG_DEVELOPER
		if (rpc_type != HATCHP0_RPC || !GetGame().IsServer())
			return;

		// Команду принимает только персонаж того, кто её отправил
		if (!sender || !GetIdentity() || sender.GetId() != GetIdentity().GetId())
			return;

		Param3<int, int, int> data = new Param3<int, int, int>(0, 0, 0);
		if (!ctx.Read(data))
			return;

		CarScript car = CarScript.Cast(GetGame().GetObjectByNetworkId(data.param2, data.param3));
		HatchP0.Execute(this, data.param1, car);
#endif
	}

	// В люке — только стойка «стоя»: присев, игрок опустит ствол в крышу
	override bool CanChangeStance(int previousStance, int newStance)
	{
#ifdef DIAG_DEVELOPER
		if (m_HatchP0Linked)
			return newStance == DayZPlayerConstants.STANCEIDX_ERECT || newStance == DayZPlayerConstants.STANCEIDX_RAISEDERECT;
#endif
		return super.CanChangeStance(previousStance, newStance);
	}

	override bool CanJump()
	{
#ifdef DIAG_DEVELOPER
		if (m_HatchP0Linked)
			return false;
#endif
		return super.CanJump();
	}

	override bool CanClimb(int climbType, SHumanCommandClimbResult climbRes)
	{
#ifdef DIAG_DEVELOPER
		if (m_HatchP0Linked)
			return false;
#endif
		return super.CanClimb(climbType, climbRes);
	}
}

// -------------------------------------------------------------------------------------
// Защита от вылета: нельзя стрелять в машину, к которой привязан игрок
// -------------------------------------------------------------------------------------
modded class WeaponManager
{
	override bool CanFire(Weapon_Base wpn)
	{
#ifdef DIAG_DEVELOPER
		string reason;
		if (m_player && HatchP0.IsFireBlocked(m_player, reason))
		{
			HatchP0.ReportFireBlocked(m_player, reason);
			return false;
		}
#endif
		return super.CanFire(wpn);
	}
}

// -------------------------------------------------------------------------------------
// Выстрелы: пишем в лог состояние игрока и машины в момент выстрела
// -------------------------------------------------------------------------------------
modded class Weapon_Base
{
	override void EEFired(int muzzleType, int mode, string ammoType)
	{
		super.EEFired(muzzleType, mode, ammoType);

#ifdef DIAG_DEVELOPER
		PlayerBase player = PlayerBase.Cast(GetHierarchyRootPlayer());
		if (player && player.m_HatchP0Car)
			HatchP0.LogStatus(player, "FIRE ammo=" + ammoType);
#endif
	}
}
