import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-team-rankings',
  templateUrl: './team-rankings.component.html',
  styleUrls: ['./team-rankings.component.css']
})
export class TeamRankingsComponent implements OnInit {
  teamRankings: any[] = [];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.fetchTeamRankings();
  }

  fetchTeamRankings(): void {
    this.http.get<any>('http://localhost:8000/rankings/')
      .subscribe(response => {
        this.teamRankings = response.rankings;
      });
  }
}
