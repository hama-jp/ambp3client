# テスト環境ガイド

このドキュメントは、AMBp3clientプロジェクトのテスト環境のセットアップと使用方法を説明します。

## 目次

1. [テスト環境のセットアップ](#テスト環境のセットアップ)
2. [テストの実行](#テストの実行)
3. [テストの種類](#テストの種類)
4. [カバレッジレポート](#カバレッジレポート)
5. [継続的インテグレーション](#継続的インテグレーション)
6. [新しいテストの追加](#新しいテストの追加)

## テスト環境のセットアップ

### 前提条件

- Python 3.7以上
- pip

### 依存関係のインストール

開発用の依存関係をインストールします：

```bash
pip install -r requirements-dev.txt
```

これにより以下のツールがインストールされます：
- **pytest**: テストフレームワーク
- **pytest-cov**: コードカバレッジ測定
- **pytest-mock**: モッキングサポート
- **flake8**: コードスタイルチェッカー
- **black**: コードフォーマッター
- **bandit**: セキュリティチェッカー
- **mypy**: 型チェッカー

## テストの実行

### すべてのテストを実行

```bash
pytest
```

### 特定のテストディレクトリを実行

```bash
# ユニットテストのみ
pytest tests/unit

# 統合テストのみ
pytest tests/integration
```

### 特定のテストファイルを実行

```bash
pytest tests/unit/test_decoder.py
```

### 特定のテストクラスまたはメソッドを実行

```bash
# 特定のクラス
pytest tests/unit/test_decoder.py::TestBinDataToAscii

# 特定のメソッド
pytest tests/unit/test_decoder.py::TestBinDataToAscii::test_basic_conversion
```

### 詳細な出力で実行

```bash
pytest -v
```

### 失敗したテストのみ再実行

```bash
pytest --lf
```

## テストの種類

### ユニットテスト (tests/unit/)

個々の関数やクラスの動作をテストします。

- `test_decoder.py`: デコーダー機能のテスト
- `test_config.py`: 設定管理のテスト

### 統合テスト (tests/integration/)

複数のコンポーネントが連携して動作することをテストします。

### テストフィクスチャ (tests/fixtures/)

テストで使用するサンプルデータやヘルパー関数を提供します。

- `sample_data.py`: サンプルデータとフィクスチャ

## カバレッジレポート

### カバレッジを含めてテストを実行

```bash
pytest --cov=AmbP3 --cov-report=html --cov-report=term-missing
```

### カバレッジレポートの確認

HTMLレポートは `htmlcov/index.html` に生成されます：

```bash
# Linuxの場合
xdg-open htmlcov/index.html

# macOSの場合
open htmlcov/index.html
```

### カバレッジの目標

現在のカバレッジ: **34%**

目標:
- 短期 (1ヶ月): 50%
- 中期 (3ヶ月): 70%
- 長期 (6ヶ月): 80%以上

## コード品質チェック

### コードスタイルチェック

```bash
# flake8でスタイルチェック
flake8 .

# blackでフォーマットチェック
black --check .

# blackで自動フォーマット
black .
```

### セキュリティチェック

```bash
# banditでセキュリティ問題をチェック
bandit -r AmbP3/

# safetyで依存関係の脆弱性をチェック
safety check
```

### 型チェック

```bash
mypy AmbP3/ --ignore-missing-imports
```

## 継続的インテグレーション

### GitHub Actions

プロジェクトは `.github/workflows/test.yml` でCI/CDを設定しています。

プッシュやプルリクエストごとに以下が自動実行されます：
- ユニットテスト
- 統合テスト
- コードスタイルチェック
- セキュリティチェック
- 型チェック
- カバレッジレポート

### ローカルでCIと同じチェックを実行

```bash
# すべてのチェックを実行
./run_all_checks.sh  # (作成予定)

# または個別に実行
pytest tests/
flake8 .
black --check .
bandit -r AmbP3/
mypy AmbP3/ --ignore-missing-imports
```

## 新しいテストの追加

### テストファイルの命名規則

- ファイル名: `test_*.py`
- クラス名: `Test*`
- メソッド名: `test_*`

### テスト作成のベストプラクティス

1. **AAA パターンを使用**
   - **Arrange**: テストデータを準備
   - **Act**: テスト対象の関数を実行
   - **Assert**: 結果を検証

```python
def test_example():
    # Arrange
    test_data = "example"

    # Act
    result = function_to_test(test_data)

    # Assert
    assert result == expected_value
```

2. **明確なテスト名**
   テスト名から何をテストしているかが分かるようにします。

```python
def test_decoder_returns_none_when_input_is_none():
    # テスト実装
    pass
```

3. **フィクスチャを使用**
   再利用可能なテストデータはフィクスチャとして定義します。

```python
@pytest.fixture
def sample_config():
    return {'ip': '127.0.0.1', 'port': 5403}

def test_with_fixture(sample_config):
    assert sample_config['ip'] == '127.0.0.1'
```

4. **モックを適切に使用**
   外部依存（データベース、ネットワーク）はモックを使用します。

```python
from unittest.mock import Mock, patch

@patch('socket.socket')
def test_connection(mock_socket):
    mock_socket.return_value = Mock()
    # テスト実装
```

### ユニットテストの例

```python
"""tests/unit/test_example.py"""
import pytest
from AmbP3.example import example_function

class TestExampleFunction:
    """Tests for example_function."""

    def test_basic_case(self):
        """Test basic functionality."""
        result = example_function("input")
        assert result == "expected_output"

    def test_edge_case(self):
        """Test edge case."""
        result = example_function("")
        assert result is None

    @pytest.mark.parametrize("input,expected", [
        ("test1", "output1"),
        ("test2", "output2"),
        ("test3", "output3"),
    ])
    def test_multiple_inputs(self, input, expected):
        """Test with multiple inputs."""
        assert example_function(input) == expected
```

## トラブルシューティング

### テストが失敗する場合

1. **依存関係を確認**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

2. **キャッシュをクリア**
   ```bash
   pytest --cache-clear
   ```

3. **詳細な出力で実行**
   ```bash
   pytest -vv --tb=long
   ```

### カバレッジが測定されない場合

```bash
# .coverageファイルを削除
rm .coverage

# htmlcovディレクトリを削除
rm -rf htmlcov

# 再実行
pytest --cov=AmbP3 --cov-report=html
```

## 参考リソース

- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)

## 次のステップ

CODE_REVIEW.mdに記載されている優先度の高い改善項目：

1. ✅ テスト環境のセットアップ（完了）
2. ⏳ SQLインジェクション修正のテスト作成
3. ⏳ 認証情報管理のテスト作成
4. ⏳ エラー処理のテスト作成
5. ⏳ カバレッジ50%を目指す

---

**最終更新**: 2025-10-30
**作成者**: Claude Code
