# Справка archive: заморозка описана без имени команды

Полный Python-прогон перед вливанием fork-symphysis-flow выявил три сбоя справки.
В порции 4 операция freeze была описана общими словами без имени команды;
формулировка «выполняется» также нарушила запрет справки сообщать состояние работы.
Частичный прогон схемы не включал test_steps_md и интеграционную проверку step-help.

Исправление: явно назвать команду freeze и описать механику без слова о текущем состоянии.
Покрытие уже есть: test_apply_and_archive_sections_name_the_freeze,
test_text_does_not_say_the_step_is_running, test_real_schema_and_real_texts_fit_together.
