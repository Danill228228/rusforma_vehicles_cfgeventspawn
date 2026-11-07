// Passengers shoot from their seat, leaning out of the window.
// A real seat (HumanCommandVehicle) cannot raise a weapon and firing from it crashes the engine, so the
// player leaves the seat but stays in the normal on-foot command, linked to the car: aiming, firing,
// reloading and recoil all stay the game's own. The body stays in the seat through an animation set
// built from the game's poses (tools/build_poses.py): the capsule is outside the door, because the engine
// pushes it out of the car, and the animation moves the body back in.
// The way out and back is animated by the same set: out, the fall that leaves the seat plays the
// seat-to-window clip; back, the car's own get-in plays the window-to-seat clip. SMOOTH = 0 brings
// back the instant switch and the game's full get-in.
class CrewFire
{
	static const int JUNCTURE = 233; // kept in one byte: larger ids never arrive
	static const int RPC_TOGGLE = 8733101;
	static const int CMD_OUT = 1;
	static const int CMD_IN = 2;
	static const int TOGGLE_PAUSE_MS = 700;
	static const int SMOOTH = 1;               // 0: the old instant switch and the game's own get-in
	static const float LEAN_OUT_TIME = 0.75;   // seconds of the seat-to-window clip, LEAN_OUT_END in tools/build_poses.py
	static const int PREPARE_MS = 250;         // the other players' clients get the set before the clip starts
	static const float LOWER_TIME = 0.35;      // a raised weapon is lowered before going back in
	static const float SET_KEEP = 0.5;         // the set stays a little after the get-in, for the other clients too
	static const float MAX_STRAY = 0.8;        // metres from the link point: an obstacle pushed the player
	static const float CRASH_SPEED_DROP = 5;   // metres per second lost between checks: the car hit something
	static const float CHECK_PERIOD = 0.25;
	static const float CAPSULE_SIDE = 0.9;     // same numbers as in tools/build_poses.py
	static const float CAPSULE_DOWN = 0.12;
	static const float SET_BLEND = 0.2;
	static const float SECTOR_FROM = 40;       // degrees from straight ahead towards the player's own door
	static const float SECTOR_TO = 140;
	static const float PIN_DISTANCE = 0.03;

	//! 1 for a seat on the right of the car, -1 for the left.
	static int Side(Transport car, int seat)
	{
		vector seatMatrix[4];
		car.CrewTransform(seat, seatMatrix);
		vector pos = seatMatrix[3];
		if (pos[0] < 0)
			return -1;
		return 1;
	}

	//! Where the capsule of a player shooting from the given seat is, in car space.
	static vector LinkPoint(Transport car, int seat)
	{
		vector seatMatrix[4];
		car.CrewTransform(seat, seatMatrix);
		vector pos = seatMatrix[3];
		pos[0] = pos[0] + Side(car, seat) * CAPSULE_SIDE;
		pos[1] = pos[1] - CAPSULE_DOWN;
		return pos;
	}

	//! A seat that shares its door with a seat ahead of it sits behind fixed glass (the rear of the Niva).
	//! Rays do not see glass, so nothing would hold back a shot into the player's own car.
	static bool HasOwnDoor(CarScript car, int seat)
	{
		string door = car.GetDoorInvSlotNameFromSeatPos(seat);
		for (int i = 0; door != "" && i < seat; i++)
		{
			if (car.GetDoorInvSlotNameFromSeatPos(i) == door)
				return false;
		}
		return true;
	}

	static string SetPath(string name, int side)
	{
		if (side > 0)
			return "CrewFire/anims/i_" + name + "_r.asi";
		return "CrewFire/anims/i_" + name + "_l.asi";
	}
}

modded class PlayerBase
{
	protected bool m_CrewOut;
	protected CarScript m_CrewCar;
	protected int m_CrewSeat;
	protected int m_CrewCommand;
	protected vector m_CrewLink;
	protected int m_CrewNextToggle;
	protected float m_CrewCheckTime;
	protected float m_CrewLastSpeed;
	protected float m_CrewBodyAngle;
	protected bool m_CrewBodySet;
	protected int m_CrewSyncSide;    // tells the other players' clients which set to use
	protected int m_CrewSetSide;
	protected string m_CrewSet;
	protected float m_CrewFallTime;  // how long the seat-to-window clip has played
	protected bool m_CrewLowering;   // back in: waiting for the weapon to go down
	protected float m_CrewLowerTime;
	protected bool m_CrewEntering;   // back in: the get-in with the window-to-seat clip is playing
	protected float m_CrewEnterTime;
	protected float m_CrewSeatedTime;
	protected CarScript m_CrewPrepCar; // server: the set is on, the juncture follows at m_CrewPrepAt
	protected int m_CrewPrepSeat;
	protected int m_CrewPrepAt;

	override void Init()
	{
		super.Init();
		RegisterNetSyncVariableInt("m_CrewSyncSide", -1, 1);
	}

	override void OnVariablesSynchronized()
	{
		super.OnVariablesSynchronized();
		CrewUseSet(m_CrewSyncSide);
	}

	//! Puts the seated animation set on, or takes it off with side 0. Runs on every machine that sees the player.
	protected void CrewUseSet(int side)
	{
		string name = "";
		if (side != 0)
			name = CrewFire.SetPath(CrewFireProfiles.SetOf(GetItemInHands()), side);
		if (name == m_CrewSet)
			return;

		m_CrewSet = name;
		m_CrewSetSide = side;
		GetItemAccessor().EnableAutoAnimInstUpdateOnHandsChange(side == 0);
		if (side != 0)
			SetAnimationInstanceByName(name, CrewFire.SET_BLEND);
		else
			GetItemAccessor().OnItemInHandsChanged(true);
	}

	override void EEItemIntoHands(EntityAI item)
	{
		super.EEItemIntoHands(item);
		if (m_CrewSetSide != 0)
			CrewUseSet(m_CrewSetSide);
	}

	override void EEItemOutOfHands(EntityAI item)
	{
		super.EEItemOutOfHands(item);
		if (m_CrewSetSide != 0)
			CrewUseSet(m_CrewSetSide);
	}

	// The body stays facing the car; the aim keeps following the mouse and the animation turns the torso.
	override bool HeadingModel(float pDt, SDayZPlayerHeadingModel pModel)
	{
		if (!m_CrewOut)
			return super.HeadingModel(pDt, pModel);

		if (!m_CrewBodySet)
		{
			m_CrewBodySet = true;
			m_CrewBodyAngle = pModel.m_fOrientationAngle;
		}
		pModel.m_fOrientationAngle = m_CrewBodyAngle;
		return true;
	}

	bool CrewIsOut()
	{
		return m_CrewOut;
	}

	protected bool CrewHasAuthority()
	{
		return !g_Game.IsMultiplayer() || g_Game.IsServer();
	}

	//! Client: the player pressed the key.
	void CrewRequestToggle()
	{
		if (g_Game.IsMultiplayer())
			RPCSingleParam(CrewFire.RPC_TOGGLE, new Param1<int>(0), true);
		else
			CrewServerToggle();
	}

	override void OnRPC(PlayerIdentity sender, int rpc_type, ParamsReadContext ctx)
	{
		if (rpc_type != CrewFire.RPC_TOGGLE)
		{
			super.OnRPC(sender, rpc_type, ctx);
			return;
		}

		PlayerIdentity owner = GetIdentity();
		if (g_Game.IsServer() && sender && owner && sender.GetId() == owner.GetId())
			CrewServerToggle();
	}

	//! Server: decides what the key press means and tells both sides to do it on the same simulation step.
	void CrewServerToggle()
	{
		if (!CrewHasAuthority() || m_CrewCommand || m_CrewPrepCar != null || m_CrewLowering || m_CrewEntering || !IsAlive() || g_Game.GetTime() < m_CrewNextToggle)
			return;

		if (m_CrewOut)
		{
			CrewSend(CrewFire.CMD_IN, m_CrewCar, CrewFreeSeat());
			return;
		}

		HumanCommandVehicle hcv = GetCommand_Vehicle();
		if (!hcv || hcv.IsGettingIn() || hcv.IsGettingOut() || hcv.IsSwitchSeat())
			return;

		CarScript car = CarScript.Cast(hcv.GetTransport());
		if (!car || car.CrewDriver() == this)
			return;

		int seat = car.CrewMemberIndex(this);
		if (seat < 0 || !CrewFire.HasOwnDoor(car, seat))
			return;

		if (CrewFire.SMOOTH == 0 || !g_Game.IsMultiplayer())
		{
			CrewSend(CrewFire.CMD_OUT, car, seat);
			return;
		}

		// Every client that sees the player puts the set with the seat-to-window clip on first, otherwise
		// they would see the game's own fall for a moment. Sitting, the set changes nothing visible.
		int side = CrewFire.Side(car, seat);
		CrewUseSet(side);
		m_CrewSyncSide = side;
		SetSynchDirty();
		m_CrewPrepCar = car;
		m_CrewPrepSeat = seat;
		m_CrewPrepAt = g_Game.GetTime() + CrewFire.PREPARE_MS;
	}

	//! Server: the pause after the set went on is over.
	protected void CrewPrepared()
	{
		CarScript car = m_CrewPrepCar;
		m_CrewPrepCar = null;

		HumanCommandVehicle hcv = GetCommand_Vehicle();
		if (car && hcv && IsAlive() && CarScript.Cast(hcv.GetTransport()) == car && car.CrewMemberIndex(this) == m_CrewPrepSeat)
		{
			CrewSend(CrewFire.CMD_OUT, car, m_CrewPrepSeat);
			return;
		}

		// The player left the seat some other way meanwhile.
		CrewSetOff();
	}

	//! Takes the set off on every machine.
	protected void CrewSetOff()
	{
		CrewUseSet(0);
		if (CrewHasAuthority())
		{
			m_CrewSyncSide = 0;
			SetSynchDirty();
		}
	}

	//! Server: the seat to return to, -1 when the car is full.
	protected int CrewFreeSeat()
	{
		if (!m_CrewCar)
			return -1;
		if (!m_CrewCar.CrewMember(m_CrewSeat))
			return m_CrewSeat;

		for (int i = 0; i < m_CrewCar.CrewSize(); i++)
		{
			if (!m_CrewCar.CrewMember(i))
				return i;
		}
		return -1;
	}

	protected void CrewSend(int command, CarScript car, int seat)
	{
		m_CrewNextToggle = g_Game.GetTime() + CrewFire.TOGGLE_PAUSE_MS;

		if (!g_Game.IsMultiplayer())
		{
			m_CrewCommand = command;
			m_CrewSeat = seat;
			m_CrewCar = car;
			return;
		}

		int low = 0;
		int high = 0;
		if (car)
			car.GetNetworkID(low, high);

		ScriptJunctureData ctx = new ScriptJunctureData;
		ctx.Write(command);
		ctx.Write(seat);
		ctx.Write(low);
		ctx.Write(high);
		SendSyncJuncture(CrewFire.JUNCTURE, ctx);
	}

	override void OnSyncJuncture(int pJunctureID, ParamsReadContext pCtx)
	{
		if (pJunctureID != CrewFire.JUNCTURE)
		{
			super.OnSyncJuncture(pJunctureID, pCtx);
			return;
		}

		int low;
		int high;
		pCtx.Read(m_CrewCommand);
		pCtx.Read(m_CrewSeat);
		pCtx.Read(low);
		pCtx.Read(high);
		m_CrewCar = CarScript.Cast(g_Game.GetObjectByNetworkId(low, high));
	}

	override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
	{
		if (m_CrewCommand)
		{
			int command = m_CrewCommand;
			m_CrewCommand = 0;
			if (command == CrewFire.CMD_OUT)
				CrewStepOut();
			else
				CrewStepIn();
			return true;
		}

		if (m_CrewPrepCar && g_Game.GetTime() >= m_CrewPrepAt)
			CrewPrepared();

		if (m_CrewEntering)
			CrewEnterUpdate(pDt, pCurrentCommandID);

		if (m_CrewOut)
		{
			CrewUpdate(pDt, pCurrentCommandID);
			if (m_CrewLowering && CrewLowerUpdate(pDt))
				return true;
		}

		return super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
	}

	protected void CrewStepOut()
	{
		HumanCommandVehicle hcv = GetCommand_Vehicle();
		if (!hcv || !m_CrewCar)
			return;

		// The same way the game itself leaves a seat early when a car sinks.
		hcv.ProcessLeaveEvents();
		if (m_CrewCar.CrewMember(m_CrewSeat) == this)
			m_CrewCar.CrewGetOut(m_CrewSeat);

		m_CrewEntering = false;
		m_CrewLowering = false;
		m_CrewFallTime = 0;
		int side = CrewFire.Side(m_CrewCar, m_CrewSeat);
		CrewUseSet(side);
		if (CrewHasAuthority())
		{
			m_CrewSyncSide = side;
			SetSynchDirty();
			CrewBreakWindow();
		}

		// The animation graph leaves its vehicle branch only through an exit clip or a fall, so a fall it is.
		// In the set the fall is the seat-to-window clip; CrewUpdate lands the player when it is over.
		// The height is noted as the game does, so a landing it detects itself counts no fall.
		StartCommand_Fall(0);
		vector feet = GetPosition();
		SetFallYDiff(feet[1]);

		m_CrewLink = CrewFire.LinkPoint(m_CrewCar, m_CrewSeat);
		PhysicsEnableGravity(false);
		PhysicsSetSolid(false);
		CrewPin();

		m_CrewOut = true;
		m_CrewBodySet = false;
		m_CrewCheckTime = 0;
		m_CrewLastSpeed = GetVelocity(m_CrewCar).Length();
	}

	//! The glass stops the barrel, so it goes: a shot from a closed window starts inside the door.
	protected void CrewBreakWindow()
	{
		EntityAI door = m_CrewCar.FindAttachmentBySlotName(m_CrewCar.GetDoorInvSlotNameFromSeatPos(m_CrewSeat));
		if (door)
			door.SetHealth("Window", "", 0);
	}

	//! Is this the door the player shoots from? The barrel passes through its window.
	bool CrewIsOwnDoor(Object hit)
	{
		if (!m_CrewOut || !m_CrewCar || !hit)
			return false;
		return hit == m_CrewCar.FindAttachmentBySlotName(m_CrewCar.GetDoorInvSlotNameFromSeatPos(m_CrewSeat));
	}

	//! Is the player aiming outside the window? A shot that starts by hitting the car the player is linked to
	//! crashes the engine, on the server too. The server does not animate the arms, so the only thing all
	//! machines agree on is the aiming angle, and the rule has to rest on it alone.
	bool CrewBarrelBlocked()
	{
		HumanCommandWeapons hcw = GetCommandModifier_Weapons();
		if (!hcw)
			return true;
		float across = hcw.GetBaseAimingAngleLR() * m_CrewSetSide;
		return across < CrewFire.SECTOR_FROM || across > CrewFire.SECTOR_TO;
	}

	protected void CrewPin()
	{
		vector m[4];
		m[0] = "1 0 0";
		m[1] = "0 1 0";
		m[2] = "0 0 1";
		m[3] = m_CrewLink;
		UnlinkFromLocalSpace();
		LinkToLocalSpaceOf(m_CrewCar, m);
	}

	protected void CrewStepIn()
	{
		if (CrewFire.SMOOTH == 0 || !m_CrewCar || m_CrewSeat < 0)
		{
			CrewDetach();
			CrewGetIn();
			return;
		}

		// The window-to-seat clip starts from the lowered weapon, so a raised one goes down first.
		m_CrewLowering = IsRaised();
		m_CrewLowerTime = 0;
		if (!m_CrewLowering)
			CrewEnterSeat();
	}

	//! Back in, still outside the seat: keeps the weapon down until it is down. True when the seat was entered.
	protected bool CrewLowerUpdate(float dt)
	{
		GetInputController().OverrideRaise(HumanInputControllerOverrideType.ONE_FRAME, false);
		m_CrewLowerTime += dt;
		if (m_CrewLowerTime < CrewFire.LOWER_TIME)
			return false;

		m_CrewLowering = false;
		CrewEnterSeat();
		return true;
	}

	//! Starts the game's get-in, which plays the window-to-seat clip while the set is still on.
	protected void CrewEnterSeat()
	{
		m_CrewOut = false;
		UnlinkFromLocalSpace();
		PhysicsSetSolid(true);
		PhysicsEnableGravity(true);
		m_CrewEntering = CrewGetIn();
		m_CrewEnterTime = 0;
		m_CrewSeatedTime = -1;
		if (!m_CrewEntering)
			CrewSetOff();
	}

	protected bool CrewGetIn()
	{
		if (!m_CrewCar || m_CrewSeat < 0)
			return false;

		HumanCommandVehicle cmd = StartCommand_Vehicle(m_CrewCar, m_CrewSeat, m_CrewCar.GetSeatAnimationType(m_CrewSeat));
		if (!cmd)
			return false;
		cmd.SetVehicleType(m_CrewCar.GetAnimInstance());
		return true;
	}

	//! During the get-in: the weapon goes in with the player and the seat hides it at the end, as a seat does.
	//! The set comes off a little after, when every client has finished the clip too.
	protected void CrewEnterUpdate(float dt, int commandID)
	{
		m_CrewEnterTime += dt;
		HumanCommandVehicle hcv = GetCommand_Vehicle();
		if (commandID != DayZPlayerConstants.COMMANDID_VEHICLE || !hcv)
		{
			// A new command may show up a step late; later than that, something cut the get-in short.
			if (m_CrewEnterTime > 0.2)
			{
				m_CrewEntering = false;
				CrewSetOff();
			}
			return;
		}

		if (hcv.IsGettingIn())
		{
			GetItemAccessor().HideItemInHands(false);
			m_CrewSeatedTime = -1;
			return;
		}

		if (m_CrewSeatedTime < 0)
		{
			m_CrewSeatedTime = 0;
			TryHideItemInHands(true);
		}
		m_CrewSeatedTime += dt;
		if (m_CrewSeatedTime >= CrewFire.SET_KEEP)
		{
			m_CrewEntering = false;
			CrewSetOff();
		}
	}

	protected void CrewDetach()
	{
		m_CrewOut = false;
		m_CrewLowering = false;
		m_CrewEntering = false;
		UnlinkFromLocalSpace();
		PhysicsSetSolid(true);
		PhysicsEnableGravity(true);
		CrewSetOff();
	}

	protected void CrewUpdate(float dt, int commandID)
	{
		switch (commandID)
		{
			case DayZPlayerConstants.COMMANDID_FALL:
				// The fall is the seat-to-window clip: it lands when the clip is over.
				m_CrewFallTime += dt;
				HumanCommandFall fall = GetCommand_Fall();
				if (fall && !fall.IsLanding() && (CrewFire.SMOOTH == 0 || m_CrewFallTime >= CrewFire.LEAN_OUT_TIME))
					fall.Land(HumanCommandFall.LANDTYPE_NONE);
				break;
			case DayZPlayerConstants.COMMANDID_MOVE:
				// The seated poses replace the crouched ones.
				GetMovementState(m_MovementState);
				if (m_MovementState.m_iStanceIdx == DayZPlayerConstants.STANCEIDX_ERECT || m_MovementState.m_iStanceIdx == DayZPlayerConstants.STANCEIDX_RAISEDERECT)
					GetCommand_Move().ForceStance(DayZPlayerConstants.STANCEIDX_CROUCH);
				break;
			case DayZPlayerConstants.COMMANDID_ACTION:
			case DayZPlayerConstants.COMMANDID_MELEE:
			case DayZPlayerConstants.COMMANDID_MELEE2:
				break;
			default:
				CrewDetach(); // death, unconsciousness, water: nothing may keep a body hanging on the car
				return;
		}

		if (!m_CrewCar)
		{
			CrewDetach();
			return;
		}

		GetInputController().OverrideMovementSpeed(HumanInputControllerOverrideType.ONE_FRAME, 0);

		// Stance changes and turning shift the capsule a little; the body must not creep along the seat.
		float stray = vector.Distance(m_CrewCar.WorldToModel(GetPosition()), m_CrewLink);
		if (stray > CrewFire.PIN_DISTANCE && stray < CrewFire.MAX_STRAY)
			CrewPin();

		m_CrewCheckTime += dt;
		if (m_CrewCheckTime < CrewFire.CHECK_PERIOD || !CrewHasAuthority())
			return;

		m_CrewCheckTime = 0;
		float speed = GetVelocity(m_CrewCar).Length();
		bool crashed = m_CrewLastSpeed - speed > CrewFire.CRASH_SPEED_DROP;
		bool pushed = stray > CrewFire.MAX_STRAY;
		m_CrewLastSpeed = speed;
		if (crashed || pushed || m_CrewCar.IsDamageDestroyed())
			CrewServerToggle();
	}

	// The player stays a child of the car, so the game counts him as seated and would only let items out of the hands.
	override bool CanReceiveItemIntoHands(EntityAI item_to_hands)
	{
		if (m_CrewOut)
			return CanPickupHeavyItem(item_to_hands);
		return super.CanReceiveItemIntoHands(item_to_hands);
	}

	override bool CanJump()
	{
		if (m_CrewOut)
			return false;
		return super.CanJump();
	}

	override bool CanClimb(int climbType, SHumanCommandClimbResult climbRes)
	{
		if (m_CrewOut)
			return false;
		return super.CanClimb(climbType, climbRes);
	}

	override bool CanChangeStance(int previousStance, int newStance)
	{
		// The seated poses replace the crouched ones, so nothing else is allowed.
		if (m_CrewOut)
			return newStance == DayZPlayerConstants.STANCEIDX_CROUCH || newStance == DayZPlayerConstants.STANCEIDX_RAISEDCROUCH;
		return super.CanChangeStance(previousStance, newStance);
	}

	override void OnDisconnect()
	{
		if (m_CrewOut)
			CrewDetach();
		super.OnDisconnect();
	}
}

modded class ModItemRegisterCallbacks
{
	override void RegisterCustom(DayZPlayerType pType)
	{
		super.RegisterCustom(pType);
		CrewFireProfiles.Register(pType);
	}
}

modded class WeaponManager
{
	override bool CanFire(Weapon_Base wpn)
	{
		if (m_player.CrewIsOut() && m_player.CrewBarrelBlocked())
			return false;
		return super.CanFire(wpn);
	}
}

modded class Weapon_Base
{
	// A barrel pointing into the player's own car goes up, the same as against any other obstacle.
	override bool LiftWeaponCheckEx(PlayerBase player, out float outObstruction, out Object outHitObject)
	{
		bool lifted = super.LiftWeaponCheckEx(player, outObstruction, outHitObject);
		if (player && player.CrewIsOut() && player.CrewBarrelBlocked())
			return true;
		return lifted;
	}

	// Obstruction would keep the barrel level, and the player would see no reason why the shot does not come.
	override bool UseWeaponObstruction(PlayerBase player, float obstructionValue, Object hitObject)
	{
		if (player && player.CrewIsOut() && player.CrewBarrelBlocked())
			return false;
		return super.UseWeaponObstruction(player, obstructionValue, hitObject);
	}

	override bool LiftWeaponRaycastResultCheck(notnull RaycastRVResult res)
	{
		PlayerBase player = PlayerBase.Cast(GetHierarchyRootPlayer());
		if (player && player.CrewIsOwnDoor(res.obj))
			return false;
		return super.LiftWeaponRaycastResultCheck(res);
	}

	// The speed of the car is not the speed of the player's own steps.
	override protected void ApproximateWeaponLiftTransform(inout vector start, inout vector direction, HumanMovementState hms, HumanInputController hic, HumanCommandWeapons hcw, HumanCommandMove hcm, vector localVelocity = "0 0 0")
	{
		PlayerBase player = PlayerBase.Cast(GetHierarchyRootPlayer());
		if (player && player.CrewIsOut())
			localVelocity = vector.Zero;
		super.ApproximateWeaponLiftTransform(start, direction, hms, hic, hcw, hcm, localVelocity);
	}
}

modded class ActionGetInTransport
{
	override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
	{
		if (player.CrewIsOut())
			return false;
		return super.ActionCondition(player, target, item);
	}
}
