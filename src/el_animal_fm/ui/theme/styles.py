from __future__ import annotations

from pathlib import Path


_THEME_ICON_DIR = Path(__file__).with_name("icons").as_posix()


BASE_STYLESHEET = """
QMainWindow {
    background: #05080a;
}

QWidget {
    color: #d7faff;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 13px;
}

#HeaderBar,
#Panel,
#PlaceholderView {
    background: #061012;
    border: 1px solid #b86400;
}

#FundSignalCard {
    background: #061012;
    border: none;
}

#FundCardsScroll,
#FundCardsSurface {
    background: transparent;
    border: none;
}

#FundCardsScroll QScrollBar:vertical {
    background: #061012;
    border-left: 1px solid #173238;
    width: 10px;
    margin: 0;
}

#FundCardsScroll QScrollBar::handle:vertical {
    background: #c96d00;
    min-height: 42px;
}

#FundCardsScroll QScrollBar::add-line:vertical,
#FundCardsScroll QScrollBar::sub-line:vertical {
    height: 0;
}

#FundCardsScroll QScrollBar::add-page:vertical,
#FundCardsScroll QScrollBar::sub-page:vertical {
    background: #061012;
}

#HeaderBar {
    background: #070b0d;
}

#AppTitle {
    color: #ff9500;
    font-size: 32px;
    font-weight: 800;
}

#AppSubtitle,
#PanelTitle,
#CardIndex,
#MetricName,
#StatusLabel {
    color: #18dce8;
    font-weight: 800;
}

#HeaderChip {
    background: #080d10;
    border: 1px solid #4d5358;
    color: #d8e0e4;
    font-size: 15px;
}

#HeaderButton,
#PrimaryHeaderButton {
    background: #120d08;
    border: 1px solid #c96d00;
    color: #ff9500;
    font-weight: 800;
}

#PrimaryHeaderButton {
    border: 2px solid #ff9500;
}

#HeaderButton:hover,
#PrimaryHeaderButton:hover {
    background: #1e1409;
}

#MainNavigation::tab {
    background: #080d10;
    border: 1px solid #9b5b00;
    color: #ff9500;
    min-width: 190px;
    min-height: 36px;
    padding: 3px 18px;
}

#MainNavigation::tab:selected {
    border-color: #18dce8;
    color: #18dce8;
    background: #092024;
}

#ViewHeading,
#CardTitle {
    color: #18dce8;
    font-size: 20px;
    font-weight: 800;
}

#CardIndex {
    font-size: 18px;
}

#MetricValue,
#StatusValue {
    color: #d7faff;
    font-weight: 700;
}

#DecisionLabel {
    color: #ffcc19;
    font-size: 15px;
    font-weight: 800;
}

#DecisionTitle {
    color: #ff9500;
    font-size: 10px;
    font-weight: 800;
}

#SemaforoTitle {
    color: #18dce8;
    font-size: 10px;
    font-weight: 800;
}

#SemaforoResult {
    color: #ffcc19;
    font-size: 19px;
    font-weight: 900;
}

#EmptySurface {
    background: #050a0c;
    border: 1px solid #173238;
}

#LogLine {
    color: #b9f8ff;
    font-size: 12px;
}

#ConsoleLine {
    color: #65ff5f;
    font-size: 12px;
}

#ChartRow,
#MockRow {
    color: #d7faff;
    font-size: 13px;
}

#PipelinePanelTitle,
#PipelineFieldLabel {
    color: #18dce8;
    font-weight: 800;
}

#PipelineInnerPanel {
    background: #050a0c;
    border: 1px solid #173238;
}

#PipelineSeparator {
    color: #173238;
    background: #173238;
    max-height: 1px;
}

#PipelineCheck {
    color: #d7faff;
    spacing: 8px;
}

#PipelineCheck::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #18dce8;
    background: #061012;
}

#PipelineCheck::indicator:checked {
    background: #18dce8;
}

#PipelineInput {
    background: #061012;
    border: 1px solid #173238;
    color: #d7faff;
    min-height: 28px;
    padding-left: 8px;
}

QSpinBox#PipelineInput,
QDoubleSpinBox#PipelineInput,
QSpinBox#NewsInput,
QDoubleSpinBox#NewsInput {
    padding-right: 20px;
}

QSpinBox#PipelineInput::up-button,
QDoubleSpinBox#PipelineInput::up-button,
QSpinBox#NewsInput::up-button,
QDoubleSpinBox#NewsInput::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    background: #18dce8;
    border: none;
    border-left: 1px solid #24535a;
    border-bottom: 1px solid #24535a;
}

QSpinBox#PipelineInput::down-button,
QDoubleSpinBox#PipelineInput::down-button,
QSpinBox#NewsInput::down-button,
QDoubleSpinBox#NewsInput::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    background: #18dce8;
    border: none;
    border-left: 1px solid #24535a;
}

QSpinBox#PipelineInput::up-button:hover,
QDoubleSpinBox#PipelineInput::up-button:hover,
QSpinBox#PipelineInput::down-button:hover,
QDoubleSpinBox#PipelineInput::down-button:hover,
QSpinBox#NewsInput::up-button:hover,
QDoubleSpinBox#NewsInput::up-button:hover,
QSpinBox#NewsInput::down-button:hover,
QDoubleSpinBox#NewsInput::down-button:hover {
    background: #ff9500;
}

QSpinBox#PipelineInput::up-button:pressed,
QDoubleSpinBox#PipelineInput::up-button:pressed,
QSpinBox#PipelineInput::down-button:pressed,
QDoubleSpinBox#PipelineInput::down-button:pressed,
QSpinBox#NewsInput::up-button:pressed,
QDoubleSpinBox#NewsInput::up-button:pressed,
QSpinBox#NewsInput::down-button:pressed,
QDoubleSpinBox#NewsInput::down-button:pressed {
    background: #ffbd4a;
}

QSpinBox#PipelineInput::up-arrow,
QDoubleSpinBox#PipelineInput::up-arrow,
QSpinBox#NewsInput::up-arrow,
QDoubleSpinBox#NewsInput::up-arrow,
QSpinBox#PipelineInput::down-arrow,
QDoubleSpinBox#PipelineInput::down-arrow,
QSpinBox#NewsInput::down-arrow,
QDoubleSpinBox#NewsInput::down-arrow {
    width: 7px;
    height: 7px;
}

#PipelineValue {
    color: #d7faff;
    font-weight: 700;
}

#PipelinePrimaryButton,
#PipelineButton {
    background: #061012;
    border: 1px solid #18dce8;
    color: #18dce8;
    font-weight: 800;
}

#PipelinePrimaryButton {
    background: #120d08;
    border-color: #ff9500;
    color: #ff9500;
}

#PipelinePrimaryButton:hover,
#PipelineButton:hover {
    background: #092024;
}

#PipelineConsole {
    background: #020506;
    border: none;
    color: #b9f8ff;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 12px;
}

#NewsPanel {
    background: #050a0c;
    border: 1px solid #17646b;
}

#NewsPanelTitle,
#NewsPanelIndex {
    color: #18dce8;
    font-size: 16px;
    font-weight: 900;
}

#NewsPanelIndex {
    background: #092024;
    border: 1px solid #18dce8;
    padding: 3px 8px;
}

#NewsFieldLabel,
#NewsScriptLabel,
#NewsStatLabel {
    color: #18dce8;
    font-size: 11px;
    font-weight: 800;
}

#NewsScriptLabel {
    border-top: 1px solid #173238;
    padding-top: 6px;
}

#NewsSeparator {
    color: #173238;
    background: #173238;
    max-height: 1px;
}

#NewsInput {
    background: #061012;
    border: 1px solid #24535a;
    color: #d7faff;
    min-height: 27px;
    padding: 0 6px;
}

#NewsInput::drop-down {
    border: none;
    width: 18px;
}

QComboBox#NewsInput QAbstractItemView {
    background: #061012;
    alternate-background-color: #061012;
    color: #d7faff;
    border: 1px solid #18dce8;
    outline: 0;
    padding: 3px;
    selection-background-color: #000000;
    selection-color: #ffffff;
}

QComboBox#NewsInput QAbstractItemView::item {
    background: #061012;
    color: #d7faff;
    min-height: 26px;
    padding: 3px 8px;
}

QComboBox#NewsInput QAbstractItemView::item:selected {
    background: #000000;
    color: #ffffff;
    border-left: 3px solid #ffffff;
}

QComboBox#NewsInput QAbstractItemView::item:hover,
QComboBox#NewsInput QAbstractItemView::item:selected:hover {
    background: #000000;
    color: #ffffff;
    border-left: 3px solid #ffffff;
}

CalendarDateEdit#NewsInput {
    padding-right: 24px;
}

CalendarDateEdit#NewsInput::drop-down {
    border: none;
    width: 28px;
}

CalendarDateEdit#NewsInput::down-arrow {
    image: none;
}

#NewsCheck {
    color: #d7faff;
    spacing: 6px;
    font-size: 11px;
}

#NewsCheck::indicator {
    width: 14px;
    height: 14px;
    background: #061012;
    border: 1px solid #18dce8;
}

#NewsCheck::indicator:checked {
    background: #18dce8;
}

#NewsPrimaryButton,
#NewsButton {
    background: #061012;
    border: 1px solid #18dce8;
    color: #18dce8;
    font-weight: 900;
    padding: 4px 10px;
}

#NewsPrimaryButton {
    background: #160e06;
    border: 2px solid #ff9500;
    color: #ff9500;
}

#NewsPrimaryButton:hover,
#NewsButton:hover {
    background: #092024;
}

#NewsStat,
#NewsErrorStat {
    background: #061012;
    border: 1px solid #17646b;
}

#NewsErrorStat {
    border-color: #d94c12;
}

#NewsStatValue {
    color: #65ff5f;
    font-size: 14px;
    font-weight: 900;
}

#NewsCaptcha {
    background: #080d10;
    border: 1px solid #4d5358;
    color: #d8e0e4;
    font-size: 18px;
    letter-spacing: 4px;
    min-height: 40px;
}

#NewsSuccess {
    color: #65ff5f;
    font-size: 11px;
    font-weight: 800;
}

#NewsConsole {
    background: #020506;
    border: 1px solid #173238;
    color: #65ff5f;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 11px;
}

#DictionarySummary {
    background: #061012;
    border: 1px solid #24535a;
    color: #d7faff;
    padding: 9px;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 11px;
}

#DictionaryMuted {
    color: #8aa9ad;
    font-size: 10px;
}

#DictionaryStatus {
    color: #65ff5f;
    font-weight: 900;
    font-size: 11px;
}

#DictionaryProgress {
    background: #061012;
    border: 1px solid #24535a;
    color: #d7faff;
    min-height: 28px;
    text-align: center;
    font-weight: 900;
}

#DictionaryProgress::chunk {
    background: #18dce8;
}

#DictionaryTable {
    background: #020708;
    alternate-background-color: #061012;
    border: 1px solid #24535a;
    color: #d7faff;
    gridline-color: #173238;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 10px;
    selection-background-color: #12353a;
}

#DictionaryTable QHeaderView::section {
    background: #092024;
    border: none;
    border-right: 1px solid #24535a;
    border-bottom: 1px solid #18dce8;
    color: #18dce8;
    padding: 5px;
    font-size: 9px;
    font-weight: 900;
}

#ModelFundCard,
#ModelSubPanel {
    background: #061012;
    border: 1px solid #24535a;
}

#ModelsScroll,
#ModelsScrollSurface {
    background: transparent;
    border: none;
}

#ModelsScroll QScrollBar:vertical {
    background: #020708;
    border: 1px solid #173238;
    width: 11px;
    margin: 0;
}

#ModelsScroll QScrollBar::handle:vertical {
    background: #18dce8;
    border: 1px solid #24535a;
    min-height: 48px;
}

#ModelsScroll QScrollBar::add-line:vertical,
#ModelsScroll QScrollBar::sub-line:vertical {
    height: 0;
}

#ModelsScroll QScrollBar::add-page:vertical,
#ModelsScroll QScrollBar::sub-page:vertical {
    background: #020708;
}

#ModelsScroll QScrollBar:horizontal {
    background: #020708;
    border: 1px solid #173238;
    height: 11px;
    margin: 0;
}

#ModelsScroll QScrollBar::handle:horizontal {
    background: #18dce8;
    border: 1px solid #24535a;
    min-width: 48px;
}

#ModelsScroll QScrollBar::add-line:horizontal,
#ModelsScroll QScrollBar::sub-line:horizontal {
    width: 0;
}

#ModelTrainingPanel,
#ModelConsolePanel {
    background: #050a0c;
    border: 1px solid #17646b;
}

#ModelTrainingOptions {
    background: #061012;
    border-left: 1px solid #173238;
    padding-left: 8px;
}

#ModelScriptLabel {
    color: #8aa9ad;
    border-top: 1px solid #173238;
    padding-top: 5px;
    font-size: 10px;
}

#ModelFundCard[selected="true"] {
    background: #120d08;
    border: 2px solid #ff9500;
}

#ModelFundName {
    background: transparent;
    border: none;
    color: #18dce8;
    font-size: 11px;
    font-weight: 900;
    text-align: left;
}

#ModelFundName:hover {
    color: #ff9500;
}

#ModelMuted {
    color: #8aa9ad;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 10px;
}

#ModelSuccess {
    color: #65ff5f;
    font-size: 10px;
    font-weight: 900;
}

#ModelFundTabs,
#ModelOptunaTabs {
    background: #020708;
}

#ModelFundTabs::tab,
#ModelOptunaTabs::tab {
    background: #061012;
    border: 1px solid #24535a;
    color: #8aa9ad;
    min-height: 26px;
    padding: 0 10px;
    font-size: 9px;
}

#ModelFundTabs::tab:selected,
#ModelOptunaTabs::tab:selected {
    background: #092024;
    border-color: #18dce8;
    color: #18dce8;
}

#ModelOptunaTabs::tab:selected {
    background: #120d08;
    border-color: #ff9500;
    color: #ff9500;
}

#ModelSearchSpace {
    background: #061012;
    border: 1px solid #24535a;
    color: #18dce8;
    padding: 8px;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    font-size: 10px;
}

#ModelTimeline {
    background: #020708;
    border: 1px solid #173238;
}

#ModelDataSplit {
    min-height: 18px;
}

#ModelDataSplit::groove:horizontal {
    background: #ff9500;
    border: 1px solid #173238;
    height: 5px;
}

#ModelDataSplit::sub-page:horizontal {
    background: #18dce8;
    border: none;
}

#ModelDataSplit::add-page:horizontal {
    background: #ff9500;
    border: none;
}

#ModelDataSplit::handle:horizontal {
    background: #ff9500;
    border: 2px solid #050a0c;
    width: 14px;
    height: 14px;
    margin: -6px 0;
}

#ModelDataSplit::handle:horizontal:hover {
    background: #ffbd4a;
    border-color: #18dce8;
}

#ModelTimelineTrain {
    color: #18dce8;
    font-size: 10px;
    font-weight: 900;
}

#ModelTimelineTest {
    color: #ff9500;
    font-size: 10px;
    font-weight: 900;
}
"""

BASE_STYLESHEET += f"""
QSpinBox#PipelineInput::up-arrow,
QDoubleSpinBox#PipelineInput::up-arrow,
QSpinBox#NewsInput::up-arrow,
QDoubleSpinBox#NewsInput::up-arrow {{
    image: url({_THEME_ICON_DIR}/spin_up.svg);
    width: 8px;
    height: 6px;
}}

QSpinBox#PipelineInput::down-arrow,
QDoubleSpinBox#PipelineInput::down-arrow,
QSpinBox#NewsInput::down-arrow,
QDoubleSpinBox#NewsInput::down-arrow {{
    image: url({_THEME_ICON_DIR}/spin_down.svg);
    width: 8px;
    height: 6px;
}}
"""
