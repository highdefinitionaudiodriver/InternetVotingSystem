from __future__ import annotations

import unittest

from internet_voting_system.repository import InMemoryRepository
from internet_voting_system.repository_base import Repository
from internet_voting_system.service import VotingService
from internet_voting_system.sqlite_repository import SqliteRepository


class RepositoryProtocolTest(unittest.TestCase):
    def test_in_memory_repository_satisfies_protocol(self) -> None:
        repository = InMemoryRepository()
        self.assertIsInstance(repository, Repository)
        self.assertIs(VotingService(repository=repository).repository, repository)

    def test_sqlite_repository_satisfies_protocol(self) -> None:
        with SqliteRepository(":memory:") as repository:
            self.assertIsInstance(repository, Repository)
            self.assertIs(VotingService(repository=repository).repository, repository)


if __name__ == "__main__":
    unittest.main()
