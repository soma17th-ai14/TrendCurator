"""기본 smoke test.

테스트가 0개일 때 pytest가 exit code 5로 종료되는 것을 막기 위한 최소 테스트.
이후 실제 기능 테스트가 추가되면 이 파일은 그대로 두거나 삭제해도 무방하다.
"""


def test_smoke():
    assert True
