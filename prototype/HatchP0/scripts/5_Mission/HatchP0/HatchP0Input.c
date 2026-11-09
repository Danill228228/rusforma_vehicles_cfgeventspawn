// =====================================================================================
// HatchP0 — горячие клавиши теста (только DayZDiag).
// Все команды: зажать ЛЕВЫЙ Ctrl + клавиша цифрового блока (NumLock включён).
//
//   Ctrl+Num1  LINK        поставить в точку люка и привязать (схема CrewFire)
//   Ctrl+Num2  PLACE       поставить на крышу без привязки (тест T3)
//   Ctrl+Num3  UNLINK      отвязать, сбросить режимы
//   Ctrl+Num4  автопилот 20 км/ч
//   Ctrl+Num5  автопилот 40 км/ч
//   Ctrl+Num6  автопилот 60 км/ч
//   Ctrl+Num0  автопилот: плавная остановка
//   Ctrl+Num7  переключить «на крыше» / «в люке» (ноги на 1 м ниже крыши)
//   Ctrl+Num8  вкл/выкл блокировку ходьбы (при LINK включается сама)
//   Ctrl+Num9  DUMP — подробный срез состояния в лог
//   Ctrl+Num+  точка крепления выше на 0.1 м
//   Ctrl+Num-  точка крепления ниже на 0.1 м
// =====================================================================================

class HatchP0Input
{
	static void Poll()
	{
		if (!KeyState(KeyCode.KC_LCONTROL))
			return;

		if (GetGame().GetUIManager().GetMenu())
			return;

		Check(KeyCode.KC_NUMPAD1,	HatchP0Cmd.LINK);
		Check(KeyCode.KC_NUMPAD2,	HatchP0Cmd.PLACE);
		Check(KeyCode.KC_NUMPAD3,	HatchP0Cmd.UNLINK);
		Check(KeyCode.KC_NUMPAD4,	HatchP0Cmd.AP_20);
		Check(KeyCode.KC_NUMPAD5,	HatchP0Cmd.AP_40);
		Check(KeyCode.KC_NUMPAD6,	HatchP0Cmd.AP_60);
		Check(KeyCode.KC_NUMPAD0,	HatchP0Cmd.AP_STOP);
		Check(KeyCode.KC_NUMPAD7,	HatchP0Cmd.HATCH_MODE);
		Check(KeyCode.KC_NUMPAD8,	HatchP0Cmd.LOCK_MOVE);
		Check(KeyCode.KC_NUMPAD9,	HatchP0Cmd.DUMP);
		Check(KeyCode.KC_ADD,		HatchP0Cmd.HEIGHT_UP);
		Check(KeyCode.KC_SUBTRACT,	HatchP0Cmd.HEIGHT_DOWN);
	}

	protected static void Check(KeyCode key, int cmd)
	{
		if (!KeyState(key))
			return;

		ClearKey(key);
		HatchP0.Request(cmd);
	}
}

modded class MissionGameplay
{
	override void OnUpdate(float timeslice)
	{
		super.OnUpdate(timeslice);

#ifdef DIAG_DEVELOPER
		HatchP0Input.Poll();
#endif
	}
}
